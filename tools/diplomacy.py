"""Factions in game, and war and pacts between them (docs/SEASONS.md, "War and pacts").

Data packs can't see Open Parties and Claims' parties; tools/standings.py reads them from the saved world. Its
hourly board run (deploy/realms-standings.sh board) also gives each faction a number and writes it in game over
RCON, through sync() here. That is the in-game faction identity other features build on, and all of it:

    st.faction        score, by player name (offline players too): the number (1 to MAX_FACTIONS) of the
                      faction the player is in. No score: in no faction, or in one made since the last run.
    st.leader         score: 1 for each party's owner, the player who speaks for the faction.
    realms:factions   command storage: names.f<N>, the faction's name as the board shows it, as a text
                      component {text:"Red Monkeys"} (plain ASCII, no quotes; show it with
                      {"nbt":"names.f<N>","storage":"realms:factions","interpret":true}, as the board's text is);
                      ids.f<N>, the party's id. names.f<N> goes when the party does; ids.f<N> stays.

A number belongs to one party for the life of the world and is never given to another; a new season's world
numbers its factions again from 1. It is only as fresh as the last board run: up to an hour behind, plus the 5
minutes the saved world can be. To compare two players' factions in a pack:
    execute if score @s st.faction = @p[...] st.faction run ...      (same faction; no score never matches)
From Python, numbers(world) and names(world) read it back from the saved world.

Diplomacy, in the realms-standings data pack (generated: edit this file, not it). A faction's leader (st.leader:
its party's owner) opens /trigger diplomacy after the launch (#launched rw.day) and can, against any other faction:
    declare war    announced; kills between the two count double in the weekly Kills column (st.warkills
                   adds the second one) until Sunday's close, when every war ends; declare again to go on.
                   Not against a pact partner.
    offer a pact   announced; the other leader accepts from their menu (that ends a war between them). A pact
                   stands until either side breaks it, and a break is announced with the faction and the player.
                   At most MAX_PACTS each (rule 31: alliances, not confederations). Offers end at the close.
Each is logged in storage realms:diplomacy log; standings' Sunday close puts the week's in the Discord post
(report()) and then sends diplomacy/week_over. Claims, the griefing rules and rule 41 stay as they are.

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

FN = f"data/{NS}/function/diplomacy"
ADVANCEMENT = f"data/{NS}/advancement/diplomacy"
FACTIONS = f"{NS}:factions"
STORE = f"{NS}:diplomacy"
STORAGE_FILE = Path("data") / NS / "command_storage.dat"   # where 26.3 saves the realms namespace's storage

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
    """The realms namespace's command storage as last saved: {"factions": {...}, "diplomacy": {...}, ...};
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


def sync_commands(factions: list[Faction], scores: dict[str, dict[str, int]], storage: dict,
                  warn: Callable[[str], None] = lambda msg: None) -> list[str]:
    """The RCON commands that bring the game's faction numbers, leaders and names in line with the parties, given
    what the saved world already holds (`scores`, the saved scoreboard; `storage`, saved_storage()). Only changes
    are sent, so an hour with no new party or member sends nothing. Names first, then numbers."""
    saved = storage.get("factions", {})
    taken = {str(pid): n for key, pid in saved.get("ids", {}).items() if (n := number_of(key))}
    had_names = saved_names(storage)
    numbered = assign(factions, taken, warn)
    commands, live = [], {}
    want = {FACTION: {}, LEADER: {}}
    for f in factions:
        n = numbered.get(f.id)
        if n is None:
            continue
        live[n] = f
        if f.id not in taken:
            commands.append(f"data modify storage {FACTIONS} ids.f{n} set value {json.dumps(f.id)}")
        if had_names.get(n) != f.name:
            commands.append(f"data modify storage {FACTIONS} names.f{n} set value {{text:{json.dumps(f.name)}}}")
        for i, player in enumerate(f.members):
            if not PLAYER_NAME.fullmatch(player):
                warn(f"{f.name}: {player!r} is not a player name; left out of its faction in game")
                continue
            want[FACTION][player] = n
            if i == 0:
                want[LEADER][player] = 1
    gone = {n for n in had_names if n not in live}
    # A faction that is gone can't be picked in the menu any more, so its pacts and wars end here (while its
    # name is still there to announce it), and its partner gets the pact back.
    pairs = {h for o in (WAR, PACT) for h, v in scores.get(o, {}).items() if v == 1}
    for holder in sorted(pairs):
        m = re.fullmatch(r"#(\d+)\.(\d+)", holder)
        if m and {int(m[1]), int(m[2])} & gone:
            commands.append(f"function {NS}:diplomacy/dissolve {{a:{int(m[1])},b:{int(m[2])}}}")
    commands += [f"data remove storage {FACTIONS} names.f{n}" for n in sorted(gone)]
    for objective, wanted in want.items():
        have = {h: v for h, v in scores.get(objective, {}).items() if not h.startswith("#")}
        commands += [f"scoreboard players set {p} {objective} {v}" for p, v in sorted(wanted.items())
                     if have.get(p) != v]
        commands += [f"scoreboard players reset {p} {objective}" for p in sorted(have) if p not in wanted]
    return commands


def sync(rcon, factions: list[Faction], scores: dict[str, dict[str, int]], world: Path,
         warn: Callable[[str], None] = lambda msg: None) -> int:
    """Sends sync_commands; stops at the first one refused (RconError). Returns how many were sent."""
    commands = sync_commands(factions, scores, saved_storage(world), warn)
    for command in commands:
        rcon(command)
    return len(commands)


# ---------------------------------------------------------------- the week's report


SAID = {"war": "{a} declared war on {b}", "pact": "{a} and {b} made a pact",
        "peace": "{a} and {b} made peace, and a pact", "break": "{a} broke its pact with {b}",
        "end": "staff ended the war or pact between {a} and {b}"}   # offers stay in game chat
REPORT_LIMIT = 10      # declarations in one Discord post


def discord_name(name: str) -> str:
    return re.sub(r"([*_~|`\\>])", r"\\\1", name)


def report(storage: dict, scores: dict[str, dict[str, int]], since: int) -> dict:
    """What the Sunday close keeps for the Discord post: {"diplomacy": lines, "diplomacy_seq": the newest
    declaration's number}. Declarations numbered above `since` (the last close's) are this week's; a log whose
    newest is below it was started again (a new world), so all of it is."""
    log = [e for e in storage.get("diplomacy", {}).get("log", []) if isinstance(e, dict)]
    newest = max((int(e.get("n", 0)) for e in log), default=0)
    since = since if newest >= since else 0
    known = saved_names(storage)

    def name(n) -> str:
        return discord_name(known.get(int(n), f"faction {n}"))
    events = [SAID[e["kind"]].format(a=name(e.get("a", 0)), b=name(e.get("b", 0)))
              for e in sorted(log, key=lambda e: int(e.get("n", 0)))
              if int(e.get("n", 0)) > since and e.get("kind") in SAID]
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
        out.append("Pacts standing: " + "; ".join(pacts) + ".")
    if any(e.get("kind") == "war" and int(e.get("n", 0)) > since for e in log):
        out.append("Every war ends with the week: a leader can declare again in game with `/trigger diplomacy`.")
    return {"diplomacy": out, "diplomacy_seq": max(newest, since)}


def discord_lines(week: dict) -> list[str]:
    """A closed week's lines for its Discord post (none for a week closed before diplomacy, or a quiet one)."""
    return list(week.get("diplomacy") or [])


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
    (f"if score #$(lo).$(hi) {WAR} matches 1", "at war", "red", [PEACE_BUTTON]),
    (f"if score #$(lo).$(hi) {PACT} matches 1", "pact", "green", [BREAK_BUTTON]),
    (f"if score #$(b).$(a) {OFFER} matches 1", "offers you a pact", "aqua", [ACCEPT_BUTTON, WAR_BUTTON]),
    (f"if score #$(a).$(b) {OFFER} matches 1", "you offered a pact", "gray", [WAR_BUTTON]),
    ("", "neutral", "gray", [WAR_BUTTON, PACT_BUTTON]),
]


def announce(*parts) -> str:
    return "$tellraw @a " + text("", *parts)


def gray(s: str) -> dict:
    return {"text": s, "color": "gray"}


def datapack_files() -> dict[str, str]:
    """The diplomacy functions and advancements; tools/standings.py puts them in the realms-standings pack."""
    f: dict[str, str] = {}
    long_cooldown = COOLDOWN_SECONDS * 20
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/diplomacy.py. Scores and storage are kept across restarts.",
        "# The faction identity tools/standings.py writes (tools/diplomacy.py says how to use it):",
        f"scoreboard objectives add {FACTION} dummy",
        f"scoreboard objectives add {LEADER} dummy",
        "# The second count of a war kill, for the weekly Kills column.",
        f"scoreboard objectives add {WARKILLS} dummy",
        f'# "#LO.HI": 1 while two factions are at war ({WAR}) or have a pact ({PACT}); "#FROM.TO": a pact offer.',
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
        "# Once, the first second after the launch (realms:rules/launch sets #launched rw.day): nothing from",
        "# before it counts. Declarations can't be made before it; this clears anything staff set by hand.",
        *(f"scoreboard players reset * {o}" for o in (WAR, PACT, OFFER, PACTS, LAST, WARKILLS)),
        f"data modify storage {STORE} log set value []",
        f"scoreboard players set #wars {STATE} 0",
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
        f"$execute if score #$(lo).$(hi) {WAR} matches 1 run " + refuse(
            "You're at war with them already, until Sunday's close."),
        f"$scoreboard players set #$(lo).$(hi) {WAR} 1",
        f"$scoreboard players reset #$(a).$(b) {OFFER}",
        f"$scoreboard players reset #$(b).$(a) {OFFER}",
        f"scoreboard players add #wars {STATE} 1",
        announce({"text": "War! ", "color": "red", "bold": True}, faction("a"), *who,
                 {"text": " declared war on ", "color": "red"}, faction("b"),
                 gray(". Kills between them count double in the weekly standings until Sunday's close. Claims "
                      "still protect, and the griefing rules still apply.")),
        "execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1",
        f'$function {NS}:diplomacy/log {{kind:"war",a:$(a),b:$(b)}}',
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
        f"$execute if score #$(b).$(a) {OFFER} matches 1 run return run function {NS}:diplomacy/accept with "
        f"storage {STORE} pair",
        f"$execute if score #$(a).$(b) {OFFER} matches 1 run " + refuse(
            "Your offer stands until they accept it, or until Sunday's close."),
        f"$scoreboard players set #$(a).$(b) {OFFER} 1",
        announce(faction("a"), *who, {"text": " offers ", "color": "aqua"}, faction("b"),
                 {"text": " a pact.", "color": "aqua"},
                 gray(" Their leader can accept it with /trigger diplomacy until Sunday's close.")),
        f'$function {NS}:diplomacy/log {{kind:"offer",a:$(a),b:$(b)}}',
        done,
    )
    f[f"{FN}/accept.mcfunction"] = lines(
        "# Macro pair {a, b, lo, hi}: faction a accepts faction b's offer. A war between them ends.",
        f"$scoreboard players reset #$(a).$(b) {OFFER}",
        f"$scoreboard players reset #$(b).$(a) {OFFER}",
        f"scoreboard players set #peace {TMP} 0",
        f"$execute if score #$(lo).$(hi) {WAR} matches 1 run scoreboard players set #peace {TMP} 1",
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
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1 run return 0",
        f"scoreboard players add @s {WARKILLS} 1",
        "title @s actionbar " + text({"text": "A war kill: it counts double this week.", "color": "red"}),
    )

    # ------------------------------------------------ the week's end and staff
    f[f"{FN}/week_over.mcfunction"] = lines(
        "# tools/standings.py close runs this once a week has closed: every war and pact offer ends; pacts stand.",
        f"execute if score #wars {STATE} matches 1.. run tellraw @a " + text(
            {"text": "The week is over, and so are its wars. ", "color": "gold"},
            gray("Pacts stand. A leader can declare war again with /trigger diplomacy.")),
        f"scoreboard players reset * {WAR}",
        f"scoreboard players reset * {OFFER}",
        f"scoreboard players set #wars {STATE} 0",
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
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1 unless score #$(lo).$(hi) {PACT} matches 1 run "
        + refuse("Those two have no war or pact."),
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(a) {PACTS} 1",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(b) {PACTS} 1",
        f"$scoreboard players reset #$(lo).$(hi) {WAR}",
        f"$scoreboard players reset #$(lo).$(hi) {PACT}",
        announce({"text": "Staff ended the war or pact between ", "color": "gold"}, faction("a"),
                 {"text": " and ", "color": "gold"}, faction("b"), {"text": ".", "color": "gold"}),
        f'$function {NS}:diplomacy/log {{kind:"end",a:$(a),b:$(b)}}',
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
        f"$execute unless score #$(lo).$(hi) {WAR} matches 1 unless score #$(lo).$(hi) {PACT} matches 1 run "
        "return 0",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(a) {PACTS} 1",
        f"$execute if score #$(lo).$(hi) {PACT} matches 1 run scoreboard players remove #f$(b) {PACTS} 1",
        f"$scoreboard players reset #$(lo).$(hi) {WAR}",
        f"$scoreboard players reset #$(lo).$(hi) {PACT}",
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
