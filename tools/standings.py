"""Weekly faction standings: one rank for every faction (an Open Parties and Claims party), from three columns.

Each column gives the faction a share of its weight, in proportion to the column's leader, rounded:

    Cup points (ev.cup, the whole season so far)     50
    Strength (its members' levels added up)          25
    PvP kills by its members this week               25   (a war enemy's count twice: tools/diplomacy.py)
    + 5 for each bounty a member claimed this week

so the leader of every column would have 100 (plus bounties). Ties on points go to more Cup points, then
more kills; still tied, they share the rank. docs/SEASONS.md, "Weekly standings", says it for players.
Land (chunks claimed) was a fourth column until November 2026 (Cup 40, land 20, Strength 20, kills 20). A week
closed then keeps its land numbers and its formula in its file and still shows with them; nothing scores land now.

    python tools/standings.py show WORLD [--state DIR]   this week so far, printed (changes nothing)
    python tools/standings.py start WORLD --state DIR    starts the first week, if none is running
    python tools/standings.py board WORLD --state DIR --docker DIR
                                                         this week so far and last week's final table on
                                                         the in-game board, and each faction's number in
                                                         game (tools/diplomacy.py)
    python tools/standings.py close WORLD --state DIR --docker DIR
                                                         ends the week: keeps its final table, starts the
                                                         next, updates the board, says so in chat and
                                                         posts the Sunday recap to Discord (after the launch)
    python tools/standings.py preview WORLD --state DIR  the Sunday recap as it would post if the week closed
                                                         now (changes nothing)
    python tools/datapacks.py                            regenerates the monkey-standings data pack (with the others)

board and close with --out FILE also write the website's standings file (deploy/monkey-standings.sh: STATUS_DIR's
standings.json, next to status.json; https://map.monkeysmp.lscaturchio.xyz/standings.json, docs/LIVE.md, "The website's
standings"), from what those runs already read. The file is public, so it holds faction names, ranks and points only:
never a member, a player's name, a coordinate, a kill count or a claim. Many players are under 18 and faction names
get no review, so it is built from an allow-list (public_rows), and STATE/hidden-names.txt lets staff hide a name. It
is never in the way of the board or the close: a write that fails is logged and they go on. Nothing is written before
the launch (#launched rw.day), so test play never shows.

WORLD is the live world folder (server/world). Everything is read from the files the server saves (every 5
minutes, and when it stops), never from RCON, which can't list parties or scores:
  data/openpartiesandclaims/parties/*.nbt          each party: its owner and members
  data/openpartiesandclaims/player-claims/*.nbt    each player's claimed chunks (never scored: for the
                                                   first-week quest's step and the recap's Land line)
  data/openpartiesandclaims/player-configs/*.toml  the party name (the owner's parties.name setting)
  data/minecraft/scoreboard.dat                     ev.cup, Strength, st.kills, st.warkills and st.bounty
  data/monkey/command_storage.dat                    the faction numbers and the week's war and pacts
  ../usercache.json                                  players' current names
Kills and bounties count from a snapshot the week starts with (STATE/week.json); each closed week is kept
in STATE/weeks/. RCON is used only to write the board, through the container's own `monkey rcon` (it finds
the password itself) in DIR, the release's docker folder. The Discord webhook is STANDINGS_WEBHOOK_URL in the
environment, else DISCORD_WEBHOOK_URL; it is never printed. The post is the Sunday recap, "Monkey SMP Weekly":
the table, then a few lines on the week (tools/recap.py). A week that closes before the launch (no
#launched rw.day yet: test play) is kept but never posted. deploy/monkey-standings.sh runs this on the VPS.

The data pack (package/monkey/datapacks/monkey-standings/, generated: edit this file, not it) counts PvP
kills outside the event arena (st.kills), holds claimed bounties (st.bounty), shows the board in chat with
/trigger standings and on text displays staff place at spawn, and has the staff bounty commands
(docs/ADMIN.md). Stdlib only (Python 3.11 or newer, for tomllib).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import wanted
from status import CLOSE_TIME, LAST_WEEK, SEASON, iso, pacific
from status import write as write_public

import diplomacy
import outposts
import recap
import saved_world
import season_calendar
from datapacks import NS, function_tag, lines, mcmeta, text
from events import ARENA_TAG, CUP, LEVEL, STRENGTH
from rcon import LIMIT, Docker, RconError
from recap import BOUNTY, DISCORD_LIMIT, KILLS, folded, gained  # one copy, so the recap counts a week as we do
from repo import Repo

DATAPACK = "monkey-standings"
FN = f"data/{NS}/function/standings"
STORE = f"{NS}:standings"   # command storage: week, last (written by this tool) and board (built from them)

WEIGHTS = (("cup", 50), ("strength", 25), ("kills", 25))
BOUNTY_POINTS = 5
MIN_WEEK_DAYS = 3     # close leaves a week younger than this alone: it was closed already (a retry, or a re-run)
TOP = 10              # factions on the board and in the Discord post
LAST_TOP = 5          # factions in last week's table on the board
NAME_LIMIT = 20       # characters of a faction's name on the board
FORMULA = ("Cup 50, Strength 25, kills this week 25 (a war enemy's count twice), each as a share of the "
           "leader; +5 a bounty; +1 an hour holding an outpost (at most 20).")


# ---------------------------------------------------------------- reading the world


def norm(text: str) -> str:
    """What names are matched on: letters and digits, lower case."""
    return "".join(c for c in text.casefold() if c.isalnum())


@dataclass
class Party:
    id: str
    name: str
    owner: str
    members: list[str]   # current names, the owner first
    uuids: list[str]


@dataclass
class World:
    parties: list[Party]
    claims: dict[str, int]                # player UUID -> chunks claimed (the quest's step, the recap: never scored)
    scores: dict[str, dict[str, int]]     # objective -> holder -> score
    labels: dict[str, str]                # Cup holder -> the name staff gave it (cup/faction)
    numbers: dict[str, int] = field(default_factory=dict)   # party id -> faction number (tools/diplomacy.py)


def usernames(world: Path) -> dict[str, str]:
    cache = world.parent / "usercache.json"
    if not cache.is_file():
        return {}
    try:
        entries = json.loads(cache.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {str(e["uuid"]).lower(): e["name"] for e in entries if isinstance(e, dict) and "uuid" in e and "name" in e}


def read_parties(world: Path, names: dict[str, str]) -> list[Party]:
    found = saved_world.parties(world)
    if found is None:
        warn(f"no {world / saved_world.PARTIES}: no factions (has a party been made with /openpac?)")
        return []
    parties = []
    for p in found:
        if p.owner is None:
            warn(f"{p.id}.nbt has no owner: left out")
            continue
        members = [names.get(m.uuid, m.username or m.uuid[:8]) for m in p.members]
        owner = members[0]
        name = saved_world.faction_name(p.name, owner)
        parties.append(Party(p.id, name, owner, members, [m.uuid for m in p.members]))
    return parties


def read_claims(world: Path) -> dict[str, int]:
    """Chunks claimed by each player, in every dimension; a claims file not named by a UUID is left out."""
    claims = {}
    for name, chunks in saved_world.claim_counts(world).items():
        try:
            claims[saved_world.uuid_text(name)] = chunks
        except ValueError:
            continue
    return claims


def read_scoreboard(world: Path) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    board = saved_world.scoreboard(world)
    if board is None:
        raise SystemExit(f"no scoreboard at {saved_world.scoreboard_path(world)}: give the world folder (server/world)")
    labels = {holder: name.strip() for holder, name in board.displays.get(CUP, {}).items()}
    return board.scores, labels


def read_world(world: Path) -> World:
    if not world.is_dir():
        raise SystemExit(f"{world} is not a folder: give the world folder (server/world)")
    scores, labels = read_scoreboard(world)
    try:
        numbers = diplomacy.numbers(world)
    except (OSError, ValueError) as e:   # faction numbers only place outpost hours: the table goes on without them
        warn(f"{e}: outpost hours are left out this run")
        numbers = {}
    return World(read_parties(world, usernames(world)), read_claims(world), scores, labels, numbers)


# ---------------------------------------------------------------- the table


@dataclass
class Row:
    name: str
    members: list[str] = field(default_factory=list)
    cup: int = 0
    land: int | None = None   # chunks claimed: only a week closed while land was a column has it (shown, not scored)
    strength: int = 0
    kills: int = 0
    bounties: int = 0
    outposts: int = 0     # whole hours an outpost was held this week (tools/outposts.py)
    points: int = 0
    rank: int = 0
    id: str = ""   # the party's (OPAC), so the recap knows a faction from last week by more than its name


def share(value: int, leader: int, weight: int) -> int:
    """weight * value / leader, rounded half up; nothing for a column nobody has anything in."""
    if leader <= 0 or value <= 0:
        return 0
    return (2 * weight * value + leader) // (2 * leader)


def rank(rows: list[Row]) -> list[Row]:
    """Points and rank for every row, best first."""
    leaders = {col: max((max(getattr(r, col), 0) for r in rows), default=0) for col, _ in WEIGHTS}
    for r in rows:
        r.points = sum(share(getattr(r, col), leaders[col], w) for col, w in WEIGHTS) + BOUNTY_POINTS * r.bounties
        r.points += outposts.points(r.outposts)

    def key(r: Row) -> tuple[int, int, int]:
        return (r.points, r.cup, r.kills)
    rows.sort(key=lambda r: (*(-k for k in key(r)), r.name.casefold()))
    for r in rows:
        r.rank = 1 + sum(1 for o in rows if key(o) > key(r))
    return rows


def match_cup(world: World, warn) -> tuple[dict[str, int], list[Row]]:
    """Cup points by party id, matching each Cup entry's id or name to a party's name or its owner's name.
    An entry that matches no party, or more than one, becomes a row of its own with only its Cup points."""
    keys: dict[str, set[str]] = {}
    for p in world.parties:
        for k in {norm(p.name), norm(p.owner)} - {""}:
            keys.setdefault(k, set()).add(p.id)
    matched: dict[str, int] = {}
    loose = []
    for holder, points in sorted(world.scores.get(CUP, {}).items()):
        if holder.startswith("#"):
            continue
        label = world.labels.get(holder) or holder
        hits = set().union(*(keys.get(k, set()) for k in {norm(holder), norm(label)} - {""}))
        if len(hits) == 1:
            pid = hits.pop()
            matched[pid] = matched.get(pid, 0) + points
        elif points:
            why = "matches no faction's name" if not hits else "matches more than one faction"
            warn(f'Cup entry {holder} ("{label}") {why}: listed on its own. Name it as the faction is named '
                 f'in /openpac (function monkey:events/cup/faction).')
            loose.append(Row(label, cup=points))
    return matched, loose


def table(world: World, baseline: dict | None, warn=lambda msg: None) -> list[Row]:
    """This week's rows: Cup and Strength as they are now, kills and bounties since `baseline`."""
    base = baseline or {}
    scores = world.scores
    kills, kills_then = scores.get(KILLS, {}), base.get("kills", {})
    war, war_then = scores.get(diplomacy.WARKILLS, {}), base.get("warkills", {})
    bounty, bounty_then = folded(scores.get(BOUNTY, {})), folded(base.get("bounty", {}))
    cup, rows = match_cup(world, warn)
    for p in world.parties:
        row = Row(p.name, list(p.members), cup=cup.get(p.id, 0), id=p.id)
        for name in p.members:
            arena = scores.get(STRENGTH, {})
            row.strength += arena[name] if name in arena else scores.get(LEVEL, {}).get(name, 0)
            row.kills += gained(kills.get(name, 0), kills_then.get(name, 0))
            row.kills += gained(war.get(name, 0), war_then.get(name, 0))   # a war enemy's kill counts twice
            row.bounties += gained(bounty.get(name.lower(), 0), bounty_then.get(name.lower(), 0))
        row.outposts = outposts.hours(scores, base.get("outposts"), world.numbers.get(p.id))
        rows.append(row)
    return rank(rows)


def record(row: Row) -> dict:
    """A row as a closed week's file keeps it. No land: only a row read back from an old week has a number there."""
    return {k: v for k, v in asdict(row).items() if not (k == "land" and v is None)}


def table_text(rows: list[Row], limit: int | None = None) -> list[str]:
    """The table in fixed-width columns (for a terminal and a Discord code block). A week closed while land was a
    column keeps its Land column."""
    shown = rows if limit is None else rows[:limit]
    land = any(r.land is not None for r in shown)
    bounty = any(r.bounties for r in shown)
    held = any(r.outposts for r in shown)
    head = f"{'#':>2}  {'Faction':<18} {'Points':>6} {'Cup':>5}" + (f" {'Land':>5}" if land else "")
    head += f" {'Str':>4} {'Kills':>5}"
    out = [head + (f" {'Bounty':>6}" if bounty else "") + (f" {'Hold':>4}" if held else "")]
    for r in shown:
        name = r.name.replace("`", "'")
        name = name if len(name) <= 18 else name[:17] + "~"
        line = f"{r.rank:>2}  {name:<18} {r.points:>6} {r.cup:>5}" + (f" {r.land or 0:>5}" if land else "")
        line += f" {r.strength:>4} {r.kills:>5}"
        out.append(line + (f" {r.bounties:>6}" if bounty else "") + (f" {r.outposts:>4}" if held else ""))
    if not rows:
        out.append("    no factions yet")
    elif limit is not None and len(rows) > limit:
        out.append(f"    and {len(rows) - limit} more")
    return out


# ---------------------------------------------------------------- the week


def day(when: dt.datetime) -> str:
    return season_calendar.short_day(when)


def clock(when: dt.datetime) -> str:
    return f"{day(when)}, {when.strftime('%I %p').lstrip('0')}"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_json(path: Path, data: dict) -> None:
    """Written whole or not at all, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def snapshot(world: World, now: dt.datetime) -> dict:
    """A new week's starting point: every player's kills (and war kills) and bounties so far, and what the recap
    counts from."""
    return {"start": now.isoformat(timespec="seconds"),
            "kills": dict(sorted(world.scores.get(KILLS, {}).items())),
            "warkills": dict(sorted(world.scores.get(diplomacy.WARKILLS, {}).items())),
            "bounty": dict(sorted(world.scores.get(BOUNTY, {}).items())),
            "recap": recap.baseline(world),
            "outposts": outposts.baseline(world.scores)}


def week_file(state: Path) -> Path:
    return state / "week.json"


def latest_week(state: Path) -> Path | None:
    weeks = sorted((state / "weeks").glob("*.json")) if (state / "weeks").is_dir() else []
    return weeks[-1] if weeks else None


def since(week: dict | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(week["start"]) if week and week.get("start") else None


def span(closed: dict) -> str:
    """'week of Sun 25 Oct to Sun 1 Nov' for a closed week."""
    end, begun = dt.datetime.fromisoformat(closed["end"]), since(closed)
    return f"week of {day(begun)} to {day(end)}" if begun else f"week ending {day(end)}"


# ---------------------------------------------------------------- the in-game board


def board_name(name: str) -> str:
    """A name the board can show: plain ASCII (the RCON path is), no quotes, at most NAME_LIMIT characters."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = " ".join("".join(c if c.isalnum() or c in " _'!?,-&%*():" else " " for c in text).split())
    return text if len(text) <= NAME_LIMIT else text[:NAME_LIMIT - 1].rstrip() + "~"


def board_line(r: Row) -> str:
    name = board_name(r.name) or board_name(r.members[0] if r.members else "") or "?"
    line = f"{r.rank}. {name}: {r.points}  [Cup {r.cup}"
    line += f", land {r.land}" if r.land is not None else ""   # last week's table, if it closed while land counted
    line += f", Str {r.strength}, kills {r.kills}"
    line += f", bounties {r.bounties}" if r.bounties else ""
    return line + (f", outposts {r.outposts}h]\n" if r.outposts else "]\n")


def section(head: str, rows: list[Row], top: int) -> dict:
    """A text component: a gray heading, then a line for each of the first `top` rows."""
    extra = [{"text": head + "\n", "color": "gray"}]
    extra += [{"text": board_line(r), "color": "gold" if r.rank == 1 else "white"} for r in rows[:top]]
    if not rows:
        extra.append({"text": "No factions yet.\n", "color": "white"})
    elif len(rows) > top:
        extra.append({"text": f"...and {len(rows) - top} more\n", "color": "gray"})
    return {"text": "", "extra": extra}


def snbt(value) -> str:
    """SNBT for what the board needs: compounds with plain keys, lists, strings, ints and booleans."""
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(value, list):
        return "[" + ",".join(snbt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{snbt(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"no SNBT for {value!r}")


def store_command(key: str, head: str, rows: list[Row], top: int) -> str:
    """The command that puts one table in the storage, with fewer rows if all of them don't fit RCON."""
    for n in range(min(top, len(rows)), -1, -1):
        command = f"data modify storage {STORE} {key} set value {snbt(section(head, rows, n))}"
        if len(command.encode()) <= LIMIT:
            return command
    raise ValueError("the board heading alone is too long for RCON")


def wanted_command(scores: dict[str, dict[str, int]]) -> str:
    """The board's Most Wanted (tools/wanted.py), from the saved scores; nothing while the wanted board is off."""
    return f"data modify storage {STORE} wanted set value {snbt(wanted.section(scores))}"


def board_commands(rows: list[Row], week: dict | None, last: dict | None, now: dt.datetime,
                   scores: dict[str, dict[str, int]] | None = None) -> list[str]:
    start = since(week)
    head = f"This week so far ({'since ' + day(start) if start else 'since the standings began'}, " \
           f"updated {clock(now)})"
    commands = [store_command("week", head, rows, TOP)]
    if last:
        then = [Row(**r) for r in last["rows"]]
        # The board's footer gives today's formula: a week scored with the land column says so in its heading.
        note = " (land still counted)" if any(r.land is not None for r in then) else ""
        commands.append(store_command("last", f"Final standings, {span(last)}{note}", then, LAST_TOP))
    commands.append(wanted_command(scores or {}))
    commands.append(f"function {NS}:standings/publish")
    return commands


def update_board(rcon, rows: list[Row], week: dict | None, last: dict | None, now: dt.datetime,
                 scores: dict[str, dict[str, int]] | None = None) -> None:
    for command in board_commands(rows, week, last, now, scores):
        rcon(command)


# ---------------------------------------------------------------- Discord


def discord_message(week: dict) -> str:
    """The Sunday recap (tools/recap.py): a closed week's table, then the lines its close kept. A week closed
    before the recap existed has none, so it posts the table alone. The formula is the one the week was scored
    with (its file keeps it), so a week closed while land counted says so when a retry posts it."""
    rows = [Row(**r) for r in week["rows"]]
    scored = week.get("formula")
    scored = scored if isinstance(scored, str) and scored else FORMULA
    head, foot = recap.heading(week), f"Scored as {scored} `/trigger standings` shows the board in game."
    bare = recap.message(head, lambda n: table_text(rows, n), [], foot, DISCORD_LIMIT)
    # The week's war and pacts come first of the sections, in the room the table leaves (cut short with MORE).
    wars = diplomacy.discord_lines(week, DISCORD_LIMIT - recap.size(bare) - 1)
    sections = [b for b in week.get("recap", []) if not (wars and b == [recap.QUIET])]   # not quiet: it had wars
    return recap.message(head, lambda n: table_text(rows, n), [wars, *sections] if wars else sections, foot,
                         DISCORD_LIMIT)


def webhook() -> str:
    return os.environ.get("STANDINGS_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK_URL") or ""


def post_discord(url: str, content: str, urlopen=urllib.request.urlopen) -> str | None:
    """Posts `content`, pinging nobody (a faction can be named @everyone). Returns what went wrong, never
    the URL or anything that could hold it."""
    if not url.startswith("https://"):
        return "the webhook setting is not an https:// URL"
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "MonkeySMP-standings/1"})
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as e:
        return f"Discord answered HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"could not reach Discord ({type(e).__name__})"
    return None


# ---------------------------------------------------------------- the website's file


PUBLIC_VERSION = 1
PUBLIC_NAME_LIMIT = 32            # characters of a faction's name in the public file
HIDDEN_NAMES = "hidden-names.txt"  # in the state folder: names staff hide, one per line
MAX_MARKS = 3                     # combining marks kept on one character: more only pile up over the text around it
ZWJ = "\u200d"                    # kept: it builds one emoji out of several, and names are compared without it
_DROPPED = {"Cc", "Cf", "Cs"}     # controls, format characters (bidi controls among them) and lone surrogates
# Unicode's other default-ignorable characters (variation selectors, but not the emoji one, U+FE0F; tags), and two more
# that draw nothing: U+3164 and its kin count as letters, U+2800 as a symbol.
_BLANK = re.compile("[\u034f\u115f\u1160\u17b4\u17b5\u180b-\u180f\u2065\u2800\u3164\ufe00-\ufe0e\uffa0\ufff0-\ufff8"
                    "\U000e0000-\U000e0fff]")
_CODE = re.compile("§[\u200d\ufe0f]*.?", re.DOTALL)   # Minecraft's formatting: a section sign, the character after it


def capped_marks(text: str) -> str:
    """Text with at most MAX_MARKS combining marks on a character. A joiner between them doesn't restart the count."""
    out, marks = [], 0
    for c in text:
        if unicodedata.category(c).startswith("M"):
            marks += 1
            if marks > MAX_MARKS:
                continue
        elif c != ZWJ:
            marks = 0
        out.append(c)
    return "".join(out)


def plain_name(value) -> str:
    """A name with no formatting, no control or invisible characters (they could reorder or hide the text around them),
    no pile of combining marks and single spaces. The invisible ones go first, so one can't split a code from its
    letter. A character this Python has no data for (category Cn) stays: it may be a new emoji. "" for what isn't a
    string."""
    if not isinstance(value, str):
        return ""
    seen = "".join(c for c in _BLANK.sub("", value) if c == ZWJ or unicodedata.category(c) not in _DROPPED)
    return " ".join(capped_marks(_CODE.sub("", seen)).split())


def public_name(value) -> str | None:
    """A name fit to show, cut to PUBLIC_NAME_LIMIT, or None: nothing there, or no letter or digit to read."""
    name = plain_name(value)[:PUBLIC_NAME_LIMIT].rstrip()
    return name if any(c.isalnum() for c in name) else None


def name_key(text: str) -> str:
    """What a name is compared on: its letters and digits, with no case or accents, and compatibility forms folded."""
    return norm(unicodedata.normalize("NFKD", text))


def hidden_names(state: Path) -> frozenset[str]:
    """The names staff hide (HIDDEN_NAMES), one per line; a line starting with # is a comment. A comment can't follow a
    name on its line, since # can be part of a name. No file: none. A byte that isn't UTF-8 spoils its own line and is
    logged. A file that can't be read at all is an error: an old file is better than a hidden name coming back."""
    try:
        text = (state / HIDDEN_NAMES).read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        return frozenset()
    if "\ufffd" in text:
        warn(f"{state / HIDDEN_NAMES} is not all UTF-8: a name with a bad byte may not match")
    names = (line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return frozenset(name_key(name) for name in map(public_name, names) if name)


def shown_name(row: dict, hidden: frozenset[str], people: frozenset[str]) -> str | None:
    """A row's name for the public file, or None: no usable name, hidden by staff, or a player's name. That is the
    name read_parties gives a party with none ("Alex's faction") or a faction or Cup entry named exactly as a player
    is, whether a member (`row`'s own) or anyone in usercache."""
    name = public_name(row.get("name"))
    if name is None or name_key(name) in hidden:
        return None
    whole = plain_name(row.get("name"))
    suffix = saved_world.UNNAMED_PARTY
    owner = whole[:-len(suffix)] if whole.casefold().endswith(suffix) else whole
    members = row.get("members")
    named = {name_key(m) for m in members if isinstance(m, str)} if isinstance(members, list) else set()
    return None if name_key(owner) in people | named else name


def public_rows(rows, hidden: frozenset[str], people: frozenset[str]) -> list[dict]:
    """The allow-list: rank, name and points, and nothing else of a row gets out. A row without a number for its rank
    and points (a closed week's file edited by hand) is left out."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        place, points = row.get("rank"), row.get("points")
        if type(place) is int and type(points) is int:   # not bool, which is an int to isinstance
            out.append({"rank": place, "name": shown_name(row, hidden, people), "points": points})
    return out


def public_last_week(state: Path, hidden: frozenset[str], people: frozenset[str]) -> dict | None:
    """The newest closed week, if it closed after the launch (test play's is no last week), with today's hidden names:
    hiding a name fixes old weeks as well. None before a first close, and for a file that can't be read."""
    try:
        week = last_launched(state)
        if week is None:
            return None
        closed = dt.datetime.fromisoformat(week["end"])
        if closed.tzinfo is None:
            raise ValueError(f"no time zone in {week['end']}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        warn(f"last week's table is left out of the public standings: {type(e).__name__}: {e}")
        return None
    return {"closed": iso(closed), "factions": public_rows(week.get("rows"), hidden, people)}


def season_closes() -> list[dt.datetime]:
    """Every Sunday 7 PM Pacific the season's week ends (monkey-standings.timer), first first: the launch weekend's,
    which status.dates() doesn't list, then each week's to the finale's."""
    return [pacific(season_calendar.week_start(week) - dt.timedelta(days=1), CLOSE_TIME)
            for week in range(1, LAST_WEEK + 2)]


def next_close(now: dt.datetime, begun: dt.datetime | None = None) -> dt.datetime | None:
    """When this week ends, or None after the season's last close. A week begun under MIN_WEEK_DAYS before a Sunday
    isn't closed that Sunday (close), so its close is the one after."""
    young = dt.timedelta(days=MIN_WEEK_DAYS)
    return next((when for when in season_closes() if when > now and (begun is None or when - begun >= young)), None)


def public_standings(world: Path, data: World, week: dict | None, state: Path, now: dt.datetime) -> dict:
    """The file's contents (the contract with the site's standings page): this week so far and last week's table."""
    hidden = hidden_names(state)
    people = frozenset(name_key(n) for n in usernames(world).values() if isinstance(n, str))
    if not people:   # without it a faction named after a player would show
        raise ValueError(f"{world.parent / 'usercache.json'} is missing or empty: players' names can't be kept out")
    closes = next_close(now, since(week))
    return {"version": PUBLIC_VERSION, "checked": iso(now), "season": SEASON,
            "week_closes": iso(closes) if closes else None,
            "factions": public_rows([asdict(r) for r in table(data, week)], hidden, people),
            "last_week": public_last_week(state, hidden, people)}


def publish(out: Path | None, world: Path, data: World, week: dict | None, state: Path, now: dt.datetime) -> int:
    """Writes the website's file, once there is a launch: 1 if that failed, for the caller to return when all else is
    done. Whatever goes wrong here, nothing is lost: the file only ever holds what the next run works out again, and the
    last good one stays up. A close's retries do the file again, and post and close nothing twice."""
    if out is None:
        return 0
    if not recap.launched(data):
        print("no public standings before the launch (#launched rw.day)")
        return 0
    try:
        write_public(out, public_standings(world, data, week, state, now))
    except Exception as e:   # anything at all: this is never worth a missed board or close
        print(f"could not write the public standings to {out}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"public standings written ({out})")
    return 0


# ---------------------------------------------------------------- the commands


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def show(world: Path, state: Path | None, now: dt.datetime) -> int:
    week = read_json(week_file(state)) if state else None
    begun = since(week)
    print(f"Faction standings this week so far ({'since ' + clock(begun) if begun else 'no week running'}; "
          f"{clock(now)})")
    print("\n".join(table_text(table(read_world(world), week, warn))))
    print(f"Scored as {FORMULA}")
    return 0


def start(world: Path, state: Path, now: dt.datetime) -> int:
    week = read_json(week_file(state))
    if week:
        begun = since(week)
        print(f"a week is already running{', since ' + clock(begun) if begun else ''}: nothing to do")
        return 0
    write_json(week_file(state), snapshot(read_world(world), now))
    print(f"started the first week at {clock(now)} ({week_file(state)})")
    return 0


def sync_factions(rcon, folder: Path, data: World) -> int:
    """Each faction's number, owner and name in game (tools/diplomacy.py), from the parties as read. A party file
    read_parties left out (no owner) is one diplomacy can't tell about, so it keeps what it has in game."""
    factions = [diplomacy.Faction(p.id, board_name(p.name) or board_name(p.owner) or p.id[:8], p.members)
                for p in data.parties]
    unsure = frozenset(p.id for p in saved_world.parties(folder) or [] if p.owner is None)
    # In the same batch: who has claimed land (the first-week quest's step), so an hour costs no extra command.
    changes = (diplomacy.sync_changes(factions, data.scores, diplomacy.saved_storage(folder), warn, unsure)
               + claimed_changes(data, usernames(folder)))
    for command in diplomacy.batch_commands(changes):
        rcon(command)
    return len(changes)


CLAIMED = "st.claimed"   # 1: the player has claimed land (the first-week quest's step, tools/quest.py)


def claimed_changes(data: World, names: dict[str, str]) -> list[dict]:
    """st.claimed 1 for each player who holds claimed chunks and doesn't have it in game yet. Never set back to
    0: giving land up later takes the step back from nobody. A UUID with no name in usercache is left out."""
    have = data.scores.get(CLAIMED, {})
    out = []
    for uuid, chunks in sorted(data.claims.items()):
        name = names.get(uuid)
        if chunks > 0 and name and have.get(name) != 1:
            out.append(diplomacy.change("sync/set", p=name, o=CLAIMED, v=1))
    return out


def board(world: Path, state: Path, rcon, now: dt.datetime, out: Path | None = None) -> int:
    week = read_json(week_file(state))
    last_path = latest_week(state)
    data = read_world(world)
    published = publish(out, world, data, week, state, now)   # first: it needs no RCON, so a stopped server gets it
    status = 0
    try:   # never in the board's way: the board goes up whatever happens here
        sent = sync_factions(rcon, world, data)
        if sent:
            print(f"factions in game: {sent} change(s) sent")
    except (RconError, OSError, ValueError) as e:
        print(f"could not write the factions in game: {e}", file=sys.stderr)
        status = 1
    try:
        update_board(rcon, table(data, week, warn), week, read_json(last_path) if last_path else None, now,
                     data.scores)
    except RconError as e:
        print(f"could not update the in-game board: {e}", file=sys.stderr)
        return 1
    print(f"board updated ({clock(now)})")
    return status or published


def closing(world: Path, data: World, rows: list[Row], week: dict | None, state: Path, now: dt.datetime,
            assume_launched: bool = False) -> dict:
    """The closed week's file: its final table, the week's war and pacts, and, after the launch, the recap's
    lines (worked out now, from the world as it is, so a retry posts the same). Before the launch it is marked
    so and never posted.
    assume_launched (preview): before the launch, the recap's lines as if the week had begun after it."""
    before = latest_week(state)
    try:
        storage = diplomacy.saved_storage(world)
    except (OSError, ValueError) as e:   # the war and pacts lines are extra: the close goes on without them
        warn(f"{e}: this week's war and pacts are left out of the post (the next one has them)")
        storage = None
    said = diplomacy.report(storage, data.scores, (read_json(before) or {}) if before else {})
    closed = {"start": week.get("start") if week else None, "end": now.isoformat(timespec="seconds"),
              "formula": FORMULA, "rows": [record(r) for r in rows], "announced": False, "posted": False,
              "launched": recap.launched(data), **said, "wars_ended": False,
              "war_ends": diplomacy.week_end(data.scores, said["diplomacy_seq"])}
    if closed["launched"] or assume_launched:
        closed["recap"] = recap.blocks(recap.Week(closed["rows"], data, week or {}, last_launched(state), now, world,
                                                  assume_launched=assume_launched and not closed["launched"]), warn)
    return closed


def last_launched(state: Path) -> dict | None:
    """The newest closed week, if it closed after the launch: test play's table is no "last week". A file from
    before the launch flag was kept tells by its end."""
    path = latest_week(state)
    previous = read_json(path) if path else None
    if previous is None:
        return None
    flag = previous.get("launched")
    after = flag is True or (flag is None and dt.datetime.fromisoformat(previous["end"]) >= season_calendar.LAUNCH)
    return previous if after else None


def preview(world: Path, state: Path, now: dt.datetime) -> int:
    week = read_json(week_file(state))
    data = read_world(world)
    closed = closing(world, data, table(data, week, warn), week, state, now, assume_launched=True)
    if not closed["launched"]:
        print("(Before the launch: a close now would keep this table and post nothing. Below is what it would say "
              "for a week begun after the launch.)\n")
    print(discord_message(closed))
    return 0


def close(world: Path, state: Path, rcon, now: dt.datetime, url: str, urlopen=urllib.request.urlopen,
          out: Path | None = None) -> int:
    """Ends the week (unless it began under MIN_WEEK_DAYS ago, so a re-run or a retry closes nothing twice), then
    does whatever the newest closed week still lacks: the board, the chat announcement, the Discord post (only
    for a week that closed after the launch). The website's file goes out once the week is closed, on every run; if it
    fails, the rest still happens and the run ends in 1, so the unit's retries try it again.
    A running server writes the world first (save-all flush, as the staff page's board button does), so a kill just
    before the close counts in the week it happened, not in the next one. A running server that won't save closes
    nothing and the run ends in 1: the unit's retries try again, and a failed unit alerts staff. A stopped server
    saved everything as it stopped, so its world on disk is read as it is."""
    try:
        if rcon.running():
            rcon("save-all flush")
    except RconError as e:
        print(f"could not save the world before the close (save-all flush): {e}. Not closing on a world that may be "
              "minutes old; the next try does it", file=sys.stderr)
        return 1
    week = read_json(week_file(state))
    start_ = since(week)
    data = read_world(world)
    rows = table(data, week, warn)
    if start_ is None or now - start_ >= dt.timedelta(days=MIN_WEEK_DAYS):
        closed = closing(world, data, rows, week, state, now)
        path = state / "weeks" / f"{now:%Y-%m-%d}.json"
        write_json(path, closed)
        week = snapshot(data, now)
        write_json(week_file(state), week)
        print(f"closed the week ({path}); a new one starts now")
        print("\n".join(table_text(rows)))
        rows = table(data, week)   # the new week: no kills or bounties yet
    else:
        print(f"this week began {clock(start_)}, under {MIN_WEEK_DAYS} days ago: not closing it (a re-run or a "
              "retry); finishing the last closed week, if anything is left")
    status = publish(out, world, data, week, state, now)
    path = latest_week(state)
    last = read_json(path) if path else None
    if path is None or last is None:
        return status
    try:
        update_board(rcon, rows, week, last, now, data.scores)
        if last.get("announced"):
            print("board updated (already announced in chat)")
        else:
            rcon(f"function {NS}:standings/announce")
            last["announced"] = True
            write_json(path, last)
            print("board updated and announced in chat")
    except RconError as e:
        print(f"could not update the in-game board: {e}", file=sys.stderr)
        status = 1
    if not last.get("wars_ended", True):   # a week closed before diplomacy has no wars to end
        try:   # the closed week's own wars (war_ends), so a late retry never ends one of the new week
            for command in diplomacy.batch_commands(last.get("war_ends") or []):
                rcon(command)
            last["wars_ended"] = True
            write_json(path, last)
            print("the week's wars are over")
        except RconError as e:
            print(f"could not end the week's wars: {e}", file=sys.stderr)
            status = 1
    if last.get("posted"):
        print("already posted to Discord")
    elif last.get("launched") is False:
        print("this week closed before the launch (test play): not posting to Discord")
    elif not url:
        print("no STANDINGS_WEBHOOK_URL or DISCORD_WEBHOOK_URL set: not posting to Discord")
    else:
        problem = post_discord(url, discord_message(last), urlopen)
        if problem:
            print(f"could not post to Discord: {problem}", file=sys.stderr)
            status = 1
        else:
            last["posted"] = True
            write_json(path, last)
            print("posted to Discord")
    return status


# ---------------------------------------------------------------- the data pack


HEADER = {"text": "Faction standings\n", "color": "gold", "bold": True}
FOOTER = {"text": f"\nScored as {FORMULA}\n/trigger standings shows this in chat.", "color": "dark_gray"}
EMPTY_WEEK = {"text": "", "extra": [{"text": "No standings yet: the first come out on Sunday evening.\n",
                                     "color": "gray"}]}
BOARD_TAG = "st.board"
DISPLAY = "minecraft:text_display"
TITLE = ("bounty_hunter", "red", "[Bounty Hunter] ")

HELP = [("place", "stand where the board goes, at spawn"), ("remove", "next to the board"),
        ('bounty/post {target:"Alex"}', "one of the top Strength holders"),
        ('bounty/claim {hunter:"Steve",target:"Alex"}', "once staff have checked the kill"),
        ("wanted/on", "players post bounties themselves (docs/SEASONS.md, Switches)"),
        ("wanted/off", "nobody can post or claim one; bounties are kept")]


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP weekly faction standings, bounties, the wanted board, war and pacts "
                              "(generated by tools/standings.py, tools/wanted.py and tools/diplomacy.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:standings/load", f"{NS}:diplomacy/load",
                                                                    f"{NS}:wanted/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:standings/tick", f"{NS}:diplomacy/tick")
    team, color, prefix = TITLE
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/standings.py. Scores, storage and the team are kept across restarts.",
        "scoreboard objectives add st.pk playerKillCount",
        f"scoreboard objectives add {KILLS} dummy",
        f"scoreboard objectives add {BOUNTY} dummy",
        "scoreboard objectives add st.ver dummy",
        "scoreboard objectives add standings trigger",
        f"scoreboard objectives add {CLAIMED} dummy",
        "# The bounty title: a team, like the supporter titles (docs/RETENTION.md). It lasts the season.",
        f"team add {team}",
        f"team modify {team} color {color}",
        f"team modify {team} prefix " + text({"text": prefix, "color": color}),
        "# Hunters are often rivals: the title must not let them see each other while invisible.",
        f"team modify {team} seeFriendlyInvisibles false",
        f"execute unless data storage {STORE} week run data modify storage {STORE} week set value {snbt(EMPTY_WEEK)}",
        f'execute unless data storage {STORE} last run data modify storage {STORE} last set value {{text:""}}',
        f'execute unless data storage {STORE} wanted run data modify storage {STORE} wanted set value {{text:""}}',
        f"function {NS}:standings/publish",
        f"schedule function {NS}:standings/second 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        "# PvP kills count for the standings, except in the event arena (its fights are for the Cup).",
        f"execute as @a[scores={{st.pk=1..}},tag=!{ARENA_TAG}] run scoreboard players operation @s {KILLS} += @s st.pk",
        "scoreboard players set @a[scores={st.pk=1..}] st.pk 0",
        f"execute as @a[scores={{standings=1..}}] run function {NS}:standings/use",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:standings/second 20t replace",
        "scoreboard players enable @a standings",
        "# A board whose chunk was unloaded when the standings changed catches up once it is loaded again.",
        f"execute as @e[type={DISPLAY},tag={BOARD_TAG}] unless score @s st.ver = #board st.ver run function "
        f"{NS}:standings/refresh",
    )
    f[f"{FN}/use.mcfunction"] = lines(
        "# Runs as a player who used /trigger standings.",
        "scoreboard players set @s standings 0",
        "scoreboard players enable @s standings",
        "tellraw @s " + text({"nbt": "board", "storage": STORE, "interpret": True}),
    )
    f[f"{FN}/publish.mcfunction"] = lines(
        "# Builds the board from the two tables tools/standings.py writes (week: this week so far; last: last",
        "# week's final standings), then every board display picks it up within a second.",
        f"data modify storage {STORE} board set value {snbt({'text': '', 'extra': [HEADER]})}",
        f"data modify storage {STORE} board.extra append from storage {STORE} week",
        "# The wanted board's Most Wanted (tools/wanted.py): empty while it is off.",
        f"data modify storage {STORE} board.extra append from storage {STORE} wanted",
        f'data modify storage {STORE} board.extra append value {{text:"\\n"}}',
        f"data modify storage {STORE} board.extra append from storage {STORE} last",
        f"data modify storage {STORE} board.extra append value {snbt(FOOTER)}",
        "scoreboard players add #board st.ver 1",
    )
    f[f"{FN}/refresh.mcfunction"] = lines(
        "# Runs as a board display that is behind.",
        f"data modify entity @s text set from storage {STORE} board",
        "scoreboard players operation @s st.ver = #board st.ver",
    )
    f[f"{FN}/announce.mcfunction"] = lines(
        "# tools/standings.py close runs this once the week's final table is on the board.",
        "tellraw @a " + text({"text": "The week's faction standings are in.\n", "color": "gold"},
                             {"nbt": "last", "storage": STORE, "interpret": True},
                             {"text": "/trigger standings shows the whole board.", "color": "gray"}),
    )
    f[f"{FN}/place.mcfunction"] = lines(
        "# Run by staff standing where the board goes (spawn). It turns to face whoever reads it.",
        f"summon {DISPLAY} ~ ~1.5 ~ {{Tags:[\"{BOARD_TAG}\"],billboard:\"vertical\",alignment:\"left\","
        "line_width:400}",
        "tellraw @s " + text({"text": "Standings board placed. To move it, run standings/remove next to it and "
                                      "place it again.", "color": "green"}),
    )
    f[f"{FN}/remove.mcfunction"] = lines(
        "# Run by staff next to a board: removes the boards within 5 blocks.",
        f"kill @e[type={DISPLAY},tag={BOARD_TAG},distance=..5]",
    )
    f.update(bounty_files())
    f.update(wanted.datapack_files())
    f.update(diplomacy.datapack_files())
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def bounty_files() -> dict[str, str]:
    """The bounty board (docs/SEASONS.md, the event catalog): staff post a bounty on a top Strength holder, and the
    player who kills them in a fair fight gets a title and standings points. Nothing sold, nothing for combat."""
    f: dict[str, str] = {}
    team = TITLE[0]
    f[f"{FN}/bounty/post.mcfunction"] = lines(
        "# Macro {target:\"Alex\"}: posts a bounty in chat.",
        "$tellraw @a " + text({"text": "Bounty posted on ", "color": "gold"}, {"text": "$(target)", "color": "white"},
                              {"text": ". Kill them in a fair fight outside the arena, then tell staff: the Bounty "
                                       f"Hunter title, and +{BOUNTY_POINTS} standings points for your faction this "
                                       "week.", "color": "gray"}),
    )
    f[f"{FN}/bounty/claim.mcfunction"] = lines(
        "# Macro {hunter:\"Steve\",target:\"Alex\"}, once staff have checked the kill: a bounty for Steve's",
        f"# faction this week (+{BOUNTY_POINTS} standings points), and the Bounty Hunter title if Steve shows no",
        "# other (a supporter color or title is never taken away for it). Run by staff in game, so the notes",
        "# reach them; over RCON only the chat line shows.",
        "tag @s add st.staff",
        f"$scoreboard players add $(hunter) {BOUNTY} 1",
        "$tellraw @a " + text({"text": "Bounty claimed: ", "color": "gold"},
                              {"text": "$(hunter)", "color": "white"},
                              {"text": " took the bounty on ", "color": "gray"},
                              {"text": "$(target)", "color": "white"},
                              {"text": f". +{BOUNTY_POINTS} standings points for their faction this week, and the "
                                       "Bounty Hunter title.", "color": "gray"}),
        f"$execute as $(hunter) if entity @s[team=] run team join {team} @s",
        f"$execute as $(hunter) unless entity @s[team={team}] run tellraw @a[tag=st.staff] " + text(
            {"text": "$(hunter) shows another title, so it stays. If they would rather show Bounty Hunter: "
                     f"team join {team} $(hunter)", "color": "yellow"}),
        "$execute unless entity $(hunter) run tellraw @a[tag=st.staff] " + text(
            {"text": "$(hunter) is offline: the points count. For the title, when they are on and show no "
                     f"other: team join {team} $(hunter)", "color": "yellow"}),
        "tag @s remove st.staff",
    )
    return f


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box.",
           "tellraw @s " + text({"text": "Standings and bounty commands (docs/ADMIN.md):", "color": "gold"})]
    for cmd, note in HELP:
        # The wanted board's are its own (tools/wanted.py); the rest are standings/<cmd>.
        full = cmd if cmd.startswith("wanted/") else f"standings/{cmd}"
        path = full.split(" ")[0]
        assert f"data/{NS}/function/{path}.mcfunction" in files, path
        out.append("tellraw @s " + text(
            {"text": f" {cmd}", "color": "aqua",
             "click_event": {"action": "suggest_command", "command": f"/function {NS}:{full}"}},
            {"text": f"  {note}", "color": "dark_gray"}))
    return lines(*out)


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weekly faction standings.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("show", "print this week so far (changes nothing)"),
                        ("start", "start the first week, if none is running"),
                        ("board", "put this week so far and last week's table on the in-game board"),
                        ("close", "end the week: keep its table, start the next, board, chat and Discord"),
                        ("preview", "print the Sunday recap as it would post if the week closed now")):
        p = sub.add_parser(name, help=about)
        p.add_argument("world", type=Path, help="the world folder (server/world)")
        p.add_argument("--state", type=Path, required=name != "show",
                       help="where the week's snapshot and the closed weeks are kept")
        if name in ("board", "close"):
            p.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")
            p.add_argument("--out", type=Path, help="also write the website's standings file here "
                                                    "(/srv/monkey/status/standings.json)")
    args = ap.parse_args(argv)
    now = season_calendar.now()
    if args.command == "show":
        return show(args.world, args.state, now)
    if args.command == "start":
        return start(args.world, args.state, now)
    if args.command == "preview":
        return preview(args.world, args.state, now)
    rcon = Docker(args.docker)
    if args.command == "board":
        return board(args.world, args.state, rcon, now, args.out)
    return close(args.world, args.state, rcon, now, webhook(), out=args.out)


if __name__ == "__main__":
    sys.exit(main())
