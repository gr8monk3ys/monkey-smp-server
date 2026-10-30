"""Factions in game, and war and pacts between them (docs/SEASONS.md, "War and pacts").

Data packs can't see Open Parties and Claims' parties; tools/standings.py reads them from the saved world. Its
hourly board run (deploy/monkey-standings.sh board) also gives each faction a number and writes it in game over
RCON, through sync() here. That is the in-game faction identity other features build on, and all of it:

    st.faction        score, by player name (offline players too): the number (1 to MAX_FACTIONS) of the
                      faction the player is in. No score: in no faction, or in one made since the last run.
    st.leader         score: 1 for each party's owner, the player who speaks for the faction.
    monkey:factions   command storage: names.f<N>, the faction's name as the board shows it, as a text
                      component {text:"Red Monkeys"} (plain ASCII, no quotes; show it with
                      {"nbt":"names.f<N>","storage":"monkey:factions","interpret":true}, as the board's text is);
                      ids.f<N>, the party's id. names.f<N> goes when the party does (missing from two runs
                      in a row, so one bad read ends nothing); ids.f<N> stays, and the name it had is kept
                      in monkey:diplomacy gone.f<N> for the Sunday post's lines about it.

A number belongs to one party for the life of the world and is never given to another; a new season's world
numbers its factions again from 1. It is only as fresh as the last board run: up to an hour behind, plus the 5
minutes the saved world can be. To compare two players' factions in a pack:
    execute if score @s st.faction = @p[...] st.faction run ...      (same faction; no score never matches)
From Python, numbers(world) and names(world) read it back from the saved world. sync() sends its changes many
to a command: a list in storage monkey:diplomacy batch that diplomacy/batch/run makes one by one.

Diplomacy, in the monkey-standings data pack (generated: edit this file, not it). A faction's leader (st.leader:
its party's owner) opens /trigger diplomacy after the launch (#launched rw.day) and can, against any other faction:
    declare war    announced; kills between the two count double in the weekly Kills column (st.warkills
                   adds the second one) until Sunday's close, when every war then running ends; declare again
                   to go on. (A war declared after the world's last save before the close runs to the next one.)
                   Not against a pact partner.
    offer a pact   announced; the other leader accepts from their menu (that ends a war between them). A pact
                   stands until either side breaks it, and a break is announced with the faction and the player.
                   At most MAX_PACTS each (rule 31: alliances, not confederations). Offers end at the close.
Each is logged in storage monkey:diplomacy log, numbered; a war's score (dp.war) and an offer's (dp.offer) is its
number there. Standings' Sunday close puts the week's in the Discord post (report()) and keeps week_end(): the
wars and offers then running, each by its number, so a late retry ends those and never a newer one; week_over
then trims the log. Claims, the griefing rules and rule 41 stay as they are.

How a war kill is counted: a hidden advancement per faction number (kill/f<N>: player_killed_entity, the victim a
player with st.faction N) runs as the killer at the kill, which knows its own faction, so the pair's war score
(dp.war "#LO.HI") decides. A scoreboard criterion can't name the victim's faction, and a log parser would need
the server's logs on the VPS and break on renamed players; the advancement needs nothing but the number.
Stdlib only, and Python 3.10 or newer.
"""
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import nbt
from challenges import LAUNCHED
from datapacks import NS, lines, refuse, text
from events import ARENA_TAG
from rcon import LIMIT

FN = f"data/{NS}/function/diplomacy"
ADVANCEMENT = f"data/{NS}/advancement/diplomacy"
FACTIONS = f"{NS}:factions"
STORE = f"{NS}:diplomacy"
STORAGE_FILE = Path("data") / NS / "command_storage.dat"   # where 26.3 saves the monkey namespace's storage

MAX_FACTIONS = 99      # numbers given in a world; /trigger diplomacy set <N><action> holds N up to 99
MAX_PACTS = 2          # pacts a faction can hold at once
COOLDOWN_SECONDS = 120 # between one faction's declarations, so chat isn't flooded

FACTION = "st.faction"
LEADER = "st.leader"
WARKILLS = "st.warkills"
TRIGGER = "diplomacy"
WAR, PACT, OFFER, PACTS, LAST, TMP, STATE = "dp.war", "dp.pact", "dp.offer", "dp.pacts", "dp.last", "dp.tmp", \
    "dp.state"
ACTIONS = {"war": 1, "pact": 2, "break": 3}   # /trigger diplomacy set N*10 + action; 1 to 9 opens the menu
PLAYER_NAME = re.compile(r"[A-Za-z0-9_]{1,16}")


# ---------------------------------------------------------------- the saved world


def saved_storage(world: Path) -> dict:
    """The monkey namespace's command storage as last saved: {"factions": {...}, "diplomacy": {...}, ...};
    {} when none is saved yet."""
    path = world / STORAGE_FILE
    if not path.is_file():
        return {}
    root = nbt.read(path)
    contents = root.get("data", root).get("contents", {}) if isinstance(root, dict) else None
    if not isinstance(contents, dict):
        raise ValueError(f"{path}: not as the server saves it (no data.contents compound)")
    return contents


def number_of(key: str) -> int | None:
    """12 for the storage key "f12"; None for anything else."""
    return int(key[1:]) if re.fullmatch(r"f[1-9]\d*", str(key)) else None


def numbers(world: Path) -> dict[str, int]:
    """Party id -> faction number, every number given in this world (a party that is gone keeps its own)."""
    ids = saved_storage(world).get("factions", {}).get("ids", {})
    return {str(pid): n for key, pid in ids.items() if (n := number_of(key))}


def name_text(value) -> str:
    """A names.f<N> value as saved ({"text": "Red Monkeys"}) -> "Red Monkeys"."""
    return str(value.get("text", "")) if isinstance(value, dict) else str(value)


def saved_names(storage: dict) -> dict[int, str]:
    """Faction number -> its name, from saved_storage()."""
    return {n: name_text(v) for key, v in storage.get("factions", {}).get("names", {}).items()
            if (n := number_of(key))}


def post_names(storage: dict) -> dict[int, str]:
    """Faction number -> its name for posts and reports: saved_names(), plus the factions that are gone, under the
    names diplomacy kept for them (monkey:diplomacy gone.f<N>), so a week's lines never say "faction N". A
    `gone` that isn't a compound (staff edited it by mistake) is ignored."""
    mine = storage.get("diplomacy", {})
    gone = mine.get("gone", {}) if isinstance(mine, dict) else {}
    out = {n: name_text(v) for key, v in gone.items() if (n := number_of(key))} if isinstance(gone, dict) else {}
    out.update({n: name for n, name in saved_names(storage).items() if name})
    return out


def names(world: Path) -> dict[int, str]:
    """Faction number -> its name, for the factions that still exist."""
    return saved_names(saved_storage(world))


# ---------------------------------------------------------------- writing the factions in game


@dataclass(frozen=True)
class Faction:
    id: str                    # the party's id (its file's name)
    name: str                  # as the board shows it
    members: list[str] = field(default_factory=list)   # player names, the owner first


def assign(factions: list[Faction], taken: dict[str, int], warn: Callable[[str], None]) -> dict[str, int]:
    """Party id -> number: the one it has, else the next never given, in party id order (so two runs on the same
    saved world give the same numbers)."""
    out = dict(taken)
    nxt = max(out.values(), default=0) + 1
    for f in sorted(factions, key=lambda f: f.id):
        if f.id in out:
            continue
        if nxt > MAX_FACTIONS:
            warn(f"{f.name}: no faction number left (all {MAX_FACTIONS} given in this world); it has no war or "
                 "pacts until a new world")
            continue
        out[f.id] = nxt
        nxt += 1
    return out


def change(f: str, **args) -> dict:
    """One change for the game to make: monkey:diplomacy/<f>, given the rest as its macro arguments."""
    return {"f": f, **args}


def sync_changes(factions: list[Faction], scores: dict[str, dict[str, int]], storage: dict,
                 warn: Callable[[str], None] = lambda msg: None, unsure: frozenset[str] = frozenset()) -> list[dict]:
    """The changes (change()) that bring the game's faction numbers, leaders and names in line with the parties,
    given what the saved world already holds (`scores`, the saved scoreboard; `storage`, saved_storage()). Only
    what differs is sent, so an hour with no new party or member sends nothing.

    A read that can't be trusted never ends a faction: with no parties read at all (the file missing or
    unreadable) nothing is sent, the parties in `unsure` (on disk but not readable) keep what they have, and a
    faction missing from a good read is only marked missing (monkey:diplomacy missing.f<N>). It ends (its war
    and pacts dissolved, its name removed) only when it is still missing on the next run."""
    saved = storage.get("factions", {})
    taken = {str(pid): n for key, pid in saved.get("ids", {}).items() if (n := number_of(key))}
    had_names = saved_names(storage)
    was_missing = {n for key in storage.get("diplomacy", {}).get("missing", {}) if (n := number_of(key))}
    if not factions and had_names:
        warn("no parties read from the saved world: can't tell which factions are gone, so nothing was changed")
        return []
    numbered = assign(factions, taken, warn)
    changes, live = [], {}
    want = {FACTION: {}, LEADER: {}}
    for f in factions:
        n = numbered.get(f.id)
        if n is None:
            continue
        live[n] = f
        if f.id not in taken:
            changes.append(change("sync/id", n=n, v=f.id))
        if had_names.get(n) != f.name:
            changes.append(change("sync/name", n=n, v=f.name))
        for i, player in enumerate(f.members):
            if not PLAYER_NAME.fullmatch(player):
                warn(f"{f.name}: {player!r} is not a player name; left out of its faction in game")
                continue
            want[FACTION][player] = n
            if i == 0:
                want[LEADER][player] = 1
    held = {taken[pid] for pid in unsure if pid in taken}
    missing = {n for n in had_names if n not in live and n not in held}
    gone, newly = missing & was_missing, missing - was_missing
    for n in sorted(newly):
        warn(f"faction {n} ({had_names[n]}) is missing from the parties read: it ends if it is still missing "
             "on the next run")
        changes.append(change("sync/missing", n=n))
    changes += [change("sync/found", n=n) for n in sorted(was_missing - missing)]
    # A faction that is gone can't be picked in the menu any more, so its pacts and wars end here (while its
    # name is still there to announce it), and its partner gets the pact back.
    pairs = {h for o in (WAR, PACT) for h, v in scores.get(o, {}).items() if v >= 1}
    for holder in sorted(pairs):
        m = re.fullmatch(r"#(\d+)\.(\d+)", holder)
        if m and {int(m[1]), int(m[2])} & gone:
            changes.append(change("dissolve", a=int(m[1]), b=int(m[2])))
    changes += [change("sync/gone", n=n) for n in sorted(gone)]
    kept = held | newly    # their players keep their number and leader until it is known
    faction_of = scores.get(FACTION, {})
    for objective, wanted in want.items():
        have = {h: v for h, v in scores.get(objective, {}).items() if not h.startswith("#")}
        changes += [change("sync/set", p=p, o=objective, v=v) for p, v in sorted(wanted.items()) if have.get(p) != v]
        changes += [change("sync/reset", p=p, o=objective) for p in sorted(have)
                    if p not in wanted and faction_of.get(p) not in kept]
    return changes


def snbt(value) -> str:
    """SNBT for a change: compounds with plain keys, strings and ints."""
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{snbt(v)}" for k, v in value.items()) + "}"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))


def batch_commands(changes: list[dict]) -> list[str]:
    """The RCON commands that make the changes: as many as fit in one command go into storage monkey:diplomacy
    batch, and monkey:diplomacy/batch/run makes them in order. Two commands for about 30 changes, so a first sync
    of every faction and member takes seconds, not one `docker compose exec` per change."""
    head, out, chunk = f"data modify storage {STORE} batch set value [", [], []

    def flush():
        out.extend([head + ",".join(chunk) + "]", f"function {NS}:diplomacy/batch/run"])

    for c in changes:
        one = snbt(c)
        if chunk and len((head + ",".join([*chunk, one]) + "]").encode()) > LIMIT:
            flush()
            chunk = []
        chunk.append(one)
    if chunk:
        flush()
    return out


def sync(rcon, factions: list[Faction], scores: dict[str, dict[str, int]], world: Path,
         warn: Callable[[str], None] = lambda msg: None, unsure: frozenset[str] = frozenset()) -> int:
    """Makes sync_changes in game; stops at the first command refused (RconError). Returns how many changes.
    A saved storage that can't be read is a ValueError (or OSError), and nothing is sent."""
    changes = sync_changes(factions, scores, saved_storage(world), warn, unsure)
    for command in batch_commands(changes):
        rcon(command)
    return len(changes)


# ---------------------------------------------------------------- the week's report


SAID = {"war": "{a} declared war on {b}", "pact": "{a} and {b} made a pact",
        "peace": "{a} and {b} made peace, and a pact", "break": "{a} broke its pact with {b}",
        "end": "staff ended the war or pact between {a} and {b}"}   # offers stay in game chat
REPORT_LIMIT = 10      # declarations in one Discord post
PACTS_LIMIT = 10       # pacts named in the "Pacts standing" line
MORE = "- and more: `/trigger diplomacy` in game"


def discord_name(name: str) -> str:
    return re.sub(r"([*_~|`\\>])", r"\\\1", name)


def more(names: list[str], limit: int) -> str:
    shown = "; ".join(names[:limit])
    return shown + (f"; and {len(names) - limit} more" if len(names) > limit else "")


def report(storage: dict | None, scores: dict[str, dict[str, int]], before: dict) -> dict:
    """What the Sunday close keeps for the Discord post: {"diplomacy": lines, "diplomacy_seq": the newest
    declaration's number, "diplomacy_world": the world's marker (#world dp.state)}. `before` is the last closed
    week (its diplomacy_seq and diplomacy_world), {} for none. The declarations numbered above its seq are this
    week's; in another world (the markers differ, a new season) all of them are. `storage` is None when the saved
    storage couldn't be read: nothing is reported, and the next close reports this week's too."""
    since, was = int(before.get("diplomacy_seq", 0) or 0), before.get("diplomacy_world")
    world = scores.get(STATE, {}).get("#world")
    if storage is None:
        return {"diplomacy": [], "diplomacy_seq": since, "diplomacy_world": was if was is not None else world}
    if world is not None and was is not None and world != was:
        since = 0
    log = [e for e in storage.get("diplomacy", {}).get("log", []) if isinstance(e, dict)]
    newest = max((int(e.get("n", 0)) for e in log), default=0)
    known, every = saved_names(storage), post_names(storage)

    def name(n) -> str:
        return discord_name(every.get(int(n)) or f"faction {n}")
    week = [e for e in sorted(log, key=lambda e: int(e.get("n", 0))) if int(e.get("n", 0)) > since]
    events = [SAID[e["kind"]].format(a=name(e.get("a", 0)), b=name(e.get("b", 0))) for e in week
              if e.get("kind") in SAID]
    pacts = []
    for holder, value in sorted(scores.get(PACT, {}).items()):
        m = re.fullmatch(r"#(\d+)\.(\d+)", holder)
        if m and value == 1 and int(m[1]) in known and int(m[2]) in known:
            pacts.append(f"{name(m[1])} and {name(m[2])}")
    out = []
    if events:
        out.append("**War and pacts this week**")
        out += [f"- {e[0].upper()}{e[1:]}" for e in events[:REPORT_LIMIT]]
        if len(events) > REPORT_LIMIT:
            out.append(f"- and {len(events) - REPORT_LIMIT} more")
    if pacts:
        out.append("Pacts standing: " + more(pacts, PACTS_LIMIT) + ".")
    if any(e.get("kind") == "war" for e in week):
        out.append("Every war ends with the week: a leader can declare again in game with `/trigger diplomacy`.")
    return {"diplomacy": out, "diplomacy_seq": max(newest, since), "diplomacy_world": world}


def week_end(scores: dict[str, dict[str, int]], seq: int) -> list[dict]:
    """The changes that end a closed week, from the scoreboard read at the close: each war and pact offer then
    running ends (only if it is still the one declared then: its score is its declaration's number, so one
    declared again since stays), then week_over announces it and trims the log up to `seq`. Kept in the closed
    week's file, so a late retry ends the same ones and never a war of the new week."""
    ends = [change("war_over", lo=int(m[1]), hi=int(m[2]), seq=v) for h, v in sorted(scores.get(WAR, {}).items())
            if v >= 1 and (m := re.fullmatch(r"#(\d+)\.(\d+)", h))]
    ends += [change("offer_over", a=int(m[1]), b=int(m[2]), seq=v) for h, v in sorted(scores.get(OFFER, {}).items())
             if v >= 1 and (m := re.fullmatch(r"#(\d+)\.(\d+)", h))]
    return [*ends, change("week_over", seq=seq)]


def discord_lines(week: dict, room: int = 2000) -> list[str]:
    """A closed week's lines for its Discord post (none for a week closed before diplomacy, or a quiet one), as
    many as fit in `room` characters (each with its newline); when they don't all fit, the first ones that fit
    with MORE after them."""
    every = list(week.get("diplomacy") or [])
    if sum(len(line) + 1 for line in every) <= room:
        return every
    out, used = [], len(MORE) + 1
    for line in every:
        if used + len(line) + 1 > room:
            break
        out.append(line)
        used += len(line) + 1
    return [*out, MORE] if used <= room else []


# ---------------------------------------------------------------- the data pack


def faction(var: str) -> dict:
    """A faction's name in chat, from the macro argument `var` (a number)."""
    return {"nbt": f"names.f$({var})", "storage": FACTIONS, "interpret": True, "color": "white"}


def button(label: str, color: str, action: str, hover: str) -> dict:
    return {"text": f" [{label}]", "color": color, "hover_event": {"action": "show_text", "value": hover},
            "click_event": {"action": "run_command", "command": f"/trigger {TRIGGER} set $(b){ACTIONS[action]}"}}


WAR_BUTTON = button("Declare war", "red", "war", "Kills between your factions count double in the weekly standings "
                    "until Sunday's close. Everyone is told.")
PACT_BUTTON = button("Offer a pact", "green", "pact", "Their leader can accept it. No war between you while it "
                     "stands. Everyone is told.")
ACCEPT_BUTTON = button("Accept the pact", "green", "pact", "No war between you while it stands. Everyone is told.")
PEACE_BUTTON = button("Offer peace and a pact", "green", "pact", "If their leader accepts, the war ends now.")
BREAK_BUTTON = button("Break the pact", "dark_red", "break", "Everyone is told, with your name.")

# The menu's line for another faction: (when, what it says, its colour, the leader's buttons).
ROWS = [
    (f"if score #$(lo).$(hi) {WAR} matches 1..", "at war", "red", [PEACE_BUTTON]),
    (f"if score #$(lo).$(hi) {PACT} matches 1", "pact", "green", [BREAK_BUTTON]),
    (f"if score #$(b).$(a) {OFFER} matches 1..", "offers you a pact", "aqua", [ACCEPT_BUTTON, WAR_BUTTON]),
    (f"if score #$(a).$(b) {OFFER} matches 1..", "you offered a pact", "gray", [WAR_BUTTON]),
    ("", "neutral", "gray", [WAR_BUTTON, PACT_BUTTON]),
]


def announce(*parts) -> str:
    return "$tellraw @a " + text("", *parts)


def gray(s: str) -> dict:
    return {"text": s, "color": "gray"}


def datapack_files() -> dict[str, str]:
    """The diplomacy functions and advancements; tools/standings.py puts them in the monkey-standings pack."""
    f: dict[str, str] = {}
    long_cooldown = COOLDOWN_SECONDS * 20
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/diplomacy.py. Scores and storage are kept across restarts.",
        "# The faction identity tools/standings.py writes (tools/diplomacy.py says how to use it):",
        f"scoreboard objectives add {FACTION} dummy",
        f"scoreboard objectives add {LEADER} dummy",
        "# The second count of a war kill, for the weekly Kills column.",
        f"scoreboard objectives add {WARKILLS} dummy",
        f'# "#LO.HI": two factions at war ({WAR}: the declaration\'s number in the log) or with a pact ({PACT}: 1);',
        f'# "#FROM.TO": a pact offer ({OFFER}: its number in the log).',
        f"scoreboard objectives add {WAR} dummy",
        f"scoreboard objectives add {PACT} dummy",
        f"scoreboard objectives add {OFFER} dummy",
        f'# "#fN": faction N\'s pacts ({PACTS}) and the game time of its last declaration ({LAST}).',
        f"scoreboard objectives add {PACTS} dummy",
        f"scoreboard objectives add {LAST} dummy",
        f"scoreboard objectives add {TMP} dummy",
        f"scoreboard objectives add {STATE} dummy",
        f"scoreboard objectives add {TRIGGER} trigger",
        f"scoreboard players set #10 {TMP} 10",
        f"execute unless data storage {STORE} log run data modify storage {STORE} log set value []",
        "# This world's marker: the Sunday report tells a new world (a new season) by it.",
        f"execute unless score #world {STATE} matches 1.. store result score #world {STATE} run random value "
        "1..2147483646",
        f"schedule function {NS}:diplomacy/second 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        f"execute as @a[scores={{{TRIGGER}=1..}}] run function {NS}:diplomacy/use",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:diplomacy/second 20t replace",
        f"scoreboard players enable @a {TRIGGER}",
        f"execute if score {LAUNCHED} matches 1 unless score #launched {STATE} matches 1 run function "
        f"{NS}:diplomacy/launch",
    )
    f[f"{FN}/launch.mcfunction"] = lines(
        "# Once, the first second after the launch (monkey:rules/launch sets #launched rw.day): nothing from",
        "# before it counts. Declarations can't be made before it; this clears anything staff set by hand.",
        *(f"scoreboard players reset * {o}" for o in (WAR, PACT, OFFER, PACTS, LAST, WARKILLS)),
        f"data modify storage {STORE} log set value []",
        f"scoreboard players set #ended {STATE} 0",
        f"scoreboard players set #launched {STATE} 1",
    )
    f[f"{FN}/pair.mcfunction"] = lines(
        f"# From #a and #b {TMP} (two faction numbers): storage {STORE} pair {{a, b, lo, hi}}, lo the smaller.",
        f"scoreboard players operation #lo {TMP} = #a {TMP}",
        f"scoreboard players operation #lo {TMP} < #b {TMP}",
        f"scoreboard players operation #hi {TMP} = #a {TMP}",
        f"scoreboard players operation #hi {TMP} > #b {TMP}",
        *(f"execute store result storage {STORE} pair.{k} int 1 run scoreboard players get #{k} {TMP}"
          for k in ("a", "b", "lo", "hi")),
    )

    # ------------------------------------------------ /trigger diplomacy
    f[f"{FN}/use.mcfunction"] = lines(
        "# Runs as a player who used /trigger diplomacy: 1 to 9 opens the menu, N*10 + action acts on faction N.",
        f"scoreboard players operation #v {TMP} = @s {TRIGGER}",
        f"scoreboard players set @s {TRIGGER} 0",
        f"scoreboard players enable @s {TRIGGER}",
        f"execute unless score {LAUNCHED} matches 1 run " + refuse("War and pacts open at the launch."),
        f"execute unless score @s {FACTION} matches 1.. run " + refuse(
            "You're in no faction the server knows yet. Make or join a party (/oparties); the server picks it up "
            "within the hour."),
        f"execute if score #v {TMP} matches ..9 run return run function {NS}:diplomacy/menu",
        f"execute unless score @s {LEADER} matches 1 run " + refuse(
            "Only your faction's leader (its party owner) can declare war or make pacts."),
        f"scoreboard players operation #act {TMP} = #v {TMP}",
        f"scoreboard players operation #act {TMP} %= #10 {TMP}",
        f"scoreboard players operation #b {TMP} = #v {TMP}",
        f"scoreboard players operation #b {TMP} /= #10 {TMP}",
        f"scoreboard players operation #a {TMP} = @s {FACTION}",
        f"execute if score #a {TMP} = #b {TMP} run " + refuse("That's your own faction."),
        f"execute unless score #b {TMP} matches 1..{MAX_FACTIONS} run " + refuse("There's no such faction."),
        f"function {NS}:diplomacy/pair",
        f"execute unless function {NS}:diplomacy/known run " + refuse("There's no such faction (any more)."),
        f"execute if function {NS}:diplomacy/cooling run " + refuse(
            f"Your faction declared something in the last {COOLDOWN_SECONDS // 60} minutes: wait a little."),
        *(f"execute if score #act {TMP} matches {n} run return run function {NS}:diplomacy/{name} with storage "
          f"{STORE} pair" for name, n in ACTIONS.items()),
        refuse("Pick from the menu: /trigger diplomacy"),
    )
    f[f"{FN}/known.mcfunction"] = lines(
        f"return run function {NS}:diplomacy/known_of with storage {STORE} pair",
    )
    f[f"{FN}/known_of.mcfunction"] = lines(
        f"$execute if data storage {FACTIONS} names.f$(b) run return 1",
        "return 0",
    )
    f[f"{FN}/cooling.mcfunction"] = lines(
        f"return run function {NS}:diplomacy/cooling_of with storage {STORE} pair",
    )
    f[f"{FN}/cooling_of.mcfunction"] = lines(
        f"# 1 when faction $(a) declared something in the last {COOLDOWN_SECONDS} seconds.",
        f"$execute unless score #f$(a) {LAST} matches -2147483648.. run return 0",
        f"execute store result score #now {TMP} run time query gametime",
        f"$scoreboard players operation #now {TMP} -= #f$(a) {LAST}",
        f"execute if score #now {TMP} matches 0..{long_cooldown - 1} run return 1",
        "return 0",
    )
    done = f"$execute store result score #f$(a) {LAST} run time query gametime"
    who = [gray(" ("), {"selector": "@s", "color": "gray"}, gray(")")]
    f[f"{FN}/war.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: faction a declares war on faction b.",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run " + refuse(
            "You have a pact with them. Break it first (everyone is told)."),
        f"$execute if score #$(lo).$(hi) {WAR} matches 1.. run " + refuse(
            "You're at war with them already, until Sunday's close."),
        f"$scoreboard players reset #$(a).$(b) {OFFER}",
        f"$scoreboard players reset #$(b).$(a) {OFFER}",
        announce({"text": "War! ", "color": "red", "bold": True}, faction("a"), *who,
                 {"text": " declared war on ", "color": "red"}, faction("b"),
                 gray(". Kills between them count double in the weekly standings until Sunday's close. Claims "
                      "still protect, and the griefing rules still apply.")),
        "execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1",
        f'$function {NS}:diplomacy/log {{kind:"war",a:$(a),b:$(b)}}',
        f"$scoreboard players operation #$(lo).$(hi) {WAR} = #seq {STATE}",
        done,
    )
    f[f"{FN}/pact.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: faction a offers faction b a pact, or accepts b's offer.",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run " + refuse("You have a pact with them already."),
        f"$execute if score #f$(a) {PACTS} matches {MAX_PACTS}.. run " + refuse(
            f"Your faction has {MAX_PACTS} pacts, the most it can hold (rule 31: alliances, not "
            "confederations). Break one first."),
        f"$execute if score #f$(b) {PACTS} matches {MAX_PACTS}.. run " + refuse(
            f"They have {MAX_PACTS} pacts, the most a faction can hold."),
        f"$execute if score #$(b).$(a) {OFFER} matches 1.. run return run function {NS}:diplomacy/accept with "
        f"storage {STORE} pair",
        f"$execute if score #$(a).$(b) {OFFER} matches 1.. run " + refuse(
            "Your offer stands until they accept it, or until Sunday's close."),
        announce(faction("a"), *who, {"text": " offers ", "color": "aqua"}, faction("b"),
                 {"text": " a pact.", "color": "aqua"},
                 gray(" Their leader can accept it with /trigger diplomacy until Sunday's close.")),
        f'$function {NS}:diplomacy/log {{kind:"offer",a:$(a),b:$(b)}}',
        f"$scoreboard players operation #$(a).$(b) {OFFER} = #seq {STATE}",
        done,
    )
    f[f"{FN}/accept.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: faction a accepts faction b's offer. A war between them ends.",
        f"$scoreboard players reset #$(a).$(b) {OFFER}",
        f"$scoreboard players reset #$(b).$(a) {OFFER}",
        f"scoreboard players set #peace {TMP} 0",
        f"$execute if score #$(lo).$(hi) {WAR} matches 1.. run scoreboard players set #peace {TMP} 1",
        f"$scoreboard players reset #$(lo).$(hi) {WAR}",
        f"$scoreboard players set #$(lo).$(hi) {PACT} 1",
        f"$scoreboard players add #f$(a) {PACTS} 1",
        f"$scoreboard players add #f$(b) {PACTS} 1",
        f"execute if score #peace {TMP} matches 1 run function {NS}:diplomacy/peace with storage {STORE} pair",
        f"execute unless score #peace {TMP} matches 1 run function {NS}:diplomacy/pact_made with storage {STORE} pair",
        done,
    )
    f[f"{FN}/peace.mcfunction"] = lines(
        announce({"text": "Peace: ", "color": "green", "bold": True}, faction("a"), *who,
                 {"text": " and ", "color": "green"}, faction("b"),
                 {"text": " ended their war with a pact.", "color": "green"},
                 gray(" It stands until either side breaks it, and a break is announced.")),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 1.2",
        f'$function {NS}:diplomacy/log {{kind:"peace",a:$(a),b:$(b)}}',
    )
    f[f"{FN}/pact_made.mcfunction"] = lines(
        announce({"text": "Pact: ", "color": "green", "bold": True}, faction("a"), *who,
                 {"text": " and ", "color": "green"}, faction("b"), {"text": " made a pact.", "color": "green"},
                 gray(" No war between them while it stands. It stands until either side breaks it, and a break "
                      "is announced.")),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 1.2",
        f'$function {NS}:diplomacy/log {{kind:"pact",a:$(a),b:$(b)}}',
    )
    f[f"{FN}/break.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: faction a breaks its pact with faction b.",
        f"$execute unless score #$(lo).$(hi) {PACT} matches 1 run " + refuse("You have no pact with them."),
        f"$scoreboard players reset #$(lo).$(hi) {PACT}",
        f"$scoreboard players remove #f$(a) {PACTS} 1",
        f"$scoreboard players remove #f$(b) {PACTS} 1",
        announce({"text": "Pact broken: ", "color": "dark_red", "bold": True}, faction("a"), *who,
                 {"text": " broke its pact with ", "color": "dark_red"}, faction("b"), gray(".")),
        "execute as @a at @s run playsound minecraft:block.anvil.land master @s ~ ~ ~ 0.4 0.8",
        f'$function {NS}:diplomacy/log {{kind:"break",a:$(a),b:$(b)}}',
        done,
    )
    f[f"{FN}/log.mcfunction"] = lines(
        "# Macro {kind, a, b}: one declaration, numbered, for the Sunday Discord post (tools/diplomacy.py report).",
        f"scoreboard players add #seq {STATE} 1",
        f'$data modify storage {STORE} log append value {{kind:"$(kind)",a:$(a),b:$(b)}}',
        f"execute store result storage {STORE} log[-1].n int 1 run scoreboard players get #seq {STATE}",
    )

    # ------------------------------------------------ the menu
    rows = [f"execute if data storage {FACTIONS} names.f{n} unless score @s {FACTION} matches {n} run function "
            f"{NS}:diplomacy/row {{b:{n}}}" for n in range(1, MAX_FACTIONS + 1)]
    f[f"{FN}/menu.mcfunction"] = lines(
        "# Runs as a player in a faction: every other faction, how yours stands with it, and (for the leader)",
        "# buttons.",
        f"execute store result storage {STORE} me.a int 1 run scoreboard players get @s {FACTION}",
        f"function {NS}:diplomacy/menu_head with storage {STORE} me",
        f"scoreboard players set #rows {TMP} 0",
        *rows,
        f"execute if score #rows {TMP} matches 0 run tellraw @s " + text(gray("No other factions yet.")),
    )
    f[f"{FN}/menu_head.mcfunction"] = lines(
        "$tellraw @s " + text("", {"text": "War and pacts", "color": "gold", "bold": True},
                              gray("  your faction: "), faction("a")),
        "tellraw @s " + text(gray(
            "A war: kills between the two count double in the weekly standings until Sunday's close (7 PM "
            "Pacific); declare again to go on. A pact: no war between the two until one side breaks it. "
            "Claims and the rules stay the same (no teaming, rule 41).")),
        f"execute unless score @s {LEADER} matches 1 run tellraw @s " + text(
            gray("Only your faction's leader (its party owner) can declare.")),
    )
    f[f"{FN}/row.mcfunction"] = lines(
        "# Macro {b}: the menu's line for faction b.",
        f"scoreboard players operation #a {TMP} = @s {FACTION}",
        f"$scoreboard players set #b {TMP} $(b)",
        f"function {NS}:diplomacy/pair",
        f"scoreboard players add #rows {TMP} 1",
        f"function {NS}:diplomacy/row_show with storage {STORE} pair",
    )
    show = ["# Macro pair {a, b, lo, hi}: the first that fits."]
    for i, (when, _, _, _) in enumerate(ROWS):
        call = f"function {NS}:diplomacy/row/{i} with storage {STORE} pair"
        show.append(f"$execute {when} run return run {call}" if when else call)
    f[f"{FN}/row_show.mcfunction"] = lines(*show)
    for i, (_, says, color, buttons) in enumerate(ROWS):
        line = ["", {"text": " - ", "color": "dark_gray"}, faction("b"), {"text": f": {says}", "color": color}]
        f[f"{FN}/row/{i}.mcfunction"] = lines(
            f"$execute if score @s {LEADER} matches 1 run return run tellraw @s " + text(*line, *buttons),
            "$tellraw @s " + text(*line),
        )

    # ------------------------------------------------ war kills
    for n in range(1, MAX_FACTIONS + 1):
        f[f"{ADVANCEMENT}/kill/f{n}.json"] = json.dumps(kill_advancement(n), indent=2)
        f[f"{FN}/kill/f{n}.mcfunction"] = lines(
            f"# A player killed a player of faction {n}: take the advancement back so the next kill fires it too.",
            f"advancement revoke @s only {NS}:diplomacy/kill/f{n}",
            f"function {NS}:diplomacy/kill {{b:{n}}}",
        )
    f[f"{FN}/kill.mcfunction"] = lines(
        "# Macro {b}, as the killer: a war enemy's kill counts twice (st.kills has the first), outside the arena,",
        "# as st.kills does, and only after the launch.",
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        f"execute if entity @s[tag={ARENA_TAG}] run return 0",
        f"execute unless score @s {FACTION} matches 1.. run return 0",
        f"scoreboard players operation #a {TMP} = @s {FACTION}",
        f"$scoreboard players set #b {TMP} $(b)",
        f"function {NS}:diplomacy/pair",
        f"function {NS}:diplomacy/war_kill with storage {STORE} pair",
    )
    f[f"{FN}/war_kill.mcfunction"] = lines(
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1.. run return 0",
        f"scoreboard players add @s {WARKILLS} 1",
        "title @s actionbar " + text({"text": "A war kill: it counts double this week.", "color": "red"}),
    )

    # ------------------------------------------------ the week's end and staff
    f[f"{FN}/war_over.mcfunction"] = lines(
        "# Macro {lo, hi, seq}: the Sunday close ends the war declared as number seq, if it still runs.",
        f"$execute unless score #$(lo).$(hi) {WAR} matches $(seq) run return 0",
        f"$scoreboard players reset #$(lo).$(hi) {WAR}",
        f"scoreboard players add #ended {STATE} 1",
    )
    f[f"{FN}/offer_over.mcfunction"] = lines(
        "# Macro {a, b, seq}: the Sunday close ends the pact offer made as number seq, if it still stands.",
        f"$execute unless score #$(a).$(b) {OFFER} matches $(seq) run return 0",
        f"$scoreboard players reset #$(a).$(b) {OFFER}",
    )
    f[f"{FN}/week_over.mcfunction"] = lines(
        "# Macro {seq}: after the close's war_over and offer_over (tools/diplomacy.py week_end): says so if a war",
        "# ended, and trims the log up to seq, the closed week's last declaration (posted to Discord).",
        f"execute if score #ended {STATE} matches 1.. run tellraw @a " + text(
            {"text": "The week is over, and so are its wars. ", "color": "gold"},
            gray("Pacts stand. A leader can declare war again with /trigger diplomacy.")),
        f"scoreboard players set #ended {STATE} 0",
        f"$scoreboard players set #trim {TMP} $(seq)",
        f"function {NS}:diplomacy/trim",
    )
    f[f"{FN}/trim.mcfunction"] = lines(
        "# Removes the log's entries numbered up to #trim dp.tmp (the log is in number order).",
        f"execute unless data storage {STORE} log[0] run return 0",
        f"execute store result score #n {TMP} run data get storage {STORE} log[0].n",
        f"execute if score #n {TMP} > #trim {TMP} run return 0",
        f"data remove storage {STORE} log[0]",
        f"function {NS}:diplomacy/trim",
    )
    f[f"{FN}/batch/run.mcfunction"] = lines(
        "# Makes the changes in storage monkey:diplomacy batch in order, each monkey:diplomacy/<f> with its entry",
        "# (tools/diplomacy.py batch_commands): many changes per RCON command.",
        f"execute unless data storage {STORE} batch[0] run return 0",
        f"function {NS}:diplomacy/batch/one with storage {STORE} batch[0]",
        f"data remove storage {STORE} batch[0]",
        f"function {NS}:diplomacy/batch/run",
    )
    f[f"{FN}/batch/one.mcfunction"] = lines(
        f"$function {NS}:diplomacy/$(f) with storage {STORE} batch[0]",
    )
    f[f"{FN}/sync/id.mcfunction"] = lines(
        f"$data modify storage {FACTIONS} ids.f$(n) set from storage {STORE} batch[0].v",
    )
    f[f"{FN}/sync/name.mcfunction"] = lines(
        f'$data modify storage {FACTIONS} names.f$(n) set value {{text:""}}',
        f"$data modify storage {FACTIONS} names.f$(n).text set from storage {STORE} batch[0].v",
    )
    f[f"{FN}/sync/missing.mcfunction"] = lines(
        "# Missing from one read of the parties: it ends only if it is still missing on the next run.",
        f"$data modify storage {STORE} missing.f$(n) set value 1b",
    )
    f[f"{FN}/sync/found.mcfunction"] = lines(
        f"$data remove storage {STORE} missing.f$(n)",
    )
    f[f"{FN}/sync/gone.mcfunction"] = lines(
        "# Missing on two runs in a row: the faction is gone (its war and pacts were dissolved just before). Its",
        "# name is kept apart, for the Sunday post's lines about its week (report()).",
        f"$data modify storage {STORE} gone.f$(n) set from storage {FACTIONS} names.f$(n)",
        f"$data remove storage {FACTIONS} names.f$(n)",
        f"$data remove storage {STORE} missing.f$(n)",
    )
    f[f"{FN}/sync/set.mcfunction"] = lines(
        "$scoreboard players set $(p) $(o) $(v)",
    )
    f[f"{FN}/sync/reset.mcfunction"] = lines(
        "$scoreboard players reset $(p) $(o)",
    )
    f[f"{FN}/staff/factions.mcfunction"] = lines(
        "# Lists every faction's number and name (names.f<N>).",
        "tellraw @s " + text({"text": "Factions by number: ", "color": "gold"},
                             {"nbt": "names", "storage": FACTIONS, "color": "white"}),
    )
    f[f"{FN}/staff/end.mcfunction"] = lines(
        "# Macro {a:3,b:7}: ends a war or a pact between factions 3 and 7 (staff/factions has the numbers), say",
        "# when one broke the rules. Announced as staff's call.",
        f"$scoreboard players set #a {TMP} $(a)",
        f"$scoreboard players set #b {TMP} $(b)",
        f"function {NS}:diplomacy/pair",
        f"function {NS}:diplomacy/staff/end_pair with storage {STORE} pair",
    )
    f[f"{FN}/staff/end_pair.mcfunction"] = lines(
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1.. unless score #$(lo).$(hi) {PACT} matches 1 run "
        + refuse("Those two have no war or pact."),
        f"function {NS}:diplomacy/end_pair with storage {STORE} pair",
        announce({"text": "Staff ended the war or pact between ", "color": "gold"}, faction("a"),
                 {"text": " and ", "color": "gold"}, faction("b"), {"text": ".", "color": "gold"}),
        f'$function {NS}:diplomacy/log {{kind:"end",a:$(a),b:$(b)}}',
    )
    f[f"{FN}/end_pair.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: ends their war and pact (staff/end_pair, dissolve_pair); both get the pact back.",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(a) {PACTS} 1",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(b) {PACTS} 1",
        f"$scoreboard players reset #$(lo).$(hi) {WAR}",
        f"$scoreboard players reset #$(lo).$(hi) {PACT}",
    )
    f[f"{FN}/dissolve.mcfunction"] = lines(
        "# Macro {a, b}: tools/standings.py sends this when one of the two factions' parties is gone: their war",
        "# or pact ends, and the other gets its pact back.",
        f"$scoreboard players set #a {TMP} $(a)",
        f"$scoreboard players set #b {TMP} $(b)",
        f"function {NS}:diplomacy/pair",
        f"function {NS}:diplomacy/dissolve_pair with storage {STORE} pair",
    )
    f[f"{FN}/dissolve_pair.mcfunction"] = lines(
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1.. unless score #$(lo).$(hi) {PACT} matches 1 run "
        "return 0",
        f"function {NS}:diplomacy/end_pair with storage {STORE} pair",
        announce({"text": "The war or pact between ", "color": "gray"}, faction("a"), gray(" and "), faction("b"),
                 gray(" is over: one of them is no longer a faction.")),
    )
    f[f"{FN}/help.mcfunction"] = lines(
        "# Lists the staff commands; click one to put it in the chat box.",
        "tellraw @s " + text({"text": "War and pacts, staff commands (docs/ADMIN.md):", "color": "gold"}),
        *("tellraw @s " + text(
            {"text": f" {cmd}", "color": "aqua",
             "click_event": {"action": "suggest_command", "command": f"/function {NS}:diplomacy/{cmd}"}},
            {"text": f"  {note}", "color": "dark_gray"})
          for cmd, note in HELP),
    )
    return f


HELP = [("staff/factions", "every faction's number and name"),
        ("staff/end {a:3,b:7}", "ends a war or pact between two factions, announced")]


def kill_advancement(n: int) -> dict:
    """Fires as a player who killed a player of faction n (26.x shapes, as tools/challenges.py's advancements)."""
    victim = {"type": "minecraft:all_of", "terms": [
        {"type": "minecraft:entity_properties", "entity": "this",
         "predicate": {"minecraft:entity_type": "minecraft:player"}},
        {"type": "minecraft:entity_scores", "entity": "this", "scores": {FACTION: {"min": n, "max": n}}},
    ]}
    return {"criteria": {"kill": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": victim}}},
            "rewards": {"function": f"{NS}:diplomacy/kill/f{n}"}}
