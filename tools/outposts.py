"""Outposts: four capture points in the newest border ring that factions take and hold for standings points.

    python tools/outposts.py status WORLD [--at TIME]     where they are, who holds them, what the timer would do
    python tools/outposts.py commands WORLD [--at TIME]   the RCON commands for now (deploy/monkey-outposts.sh)
    python tools/datapacks.py                             regenerates the monkey-outposts data pack (with the others)

Where (this script, from the saved world, as drops does; Minecraft can't see claims): one outpost in each
quarter of the newest border ring (North, East, South, West of the border's centre), on the middle of an
Overworld chunk, inside drops.ring() (past SPAWN_CLEAR blocks from spawn before the first border act; after
one, only the land it added), 64 blocks inside the border and CLAIM_GAP chunks or more from every claimed
chunk. deploy/monkey-outposts.sh sends `commands` every hour. Before the launch (#launched rw.day) there are
none. After it, the first run places all four; when a border act has finished growing (`worldborder set`) the
next run places all four again in the new ring (holders start over; hours already earned stay). In between,
an outpost with a claim within MOVE_GAP chunks moves to a new spot in its quarter (its holder keeps it), and
one that has no spot yet (none was dry land) is tried again. The pack checks the ground at each candidate in
turn, as drops does, and takes the first dry, natural one.

How (the monkey-outposts data pack, generated: edit this file, not it): a faction captures an outpost by having
members inside its square (ZONE blocks across, from BELOW blocks under the ground to ABOVE over it) with no
other faction's player there for CAPTURE_SECONDS. A player counts only by tools/diplomacy.py's faction number
(st.faction): one in no faction, or in a faction made since the last hourly board run, neither captures nor
blocks. Two factions inside: contested, and the count waits. Nobody: the attempt ends. Players in survival
only, never in the event arena. A text display over it says who holds it. The holder's members are told when
someone starts taking it, and everyone when it falls.

Points: every minute an outpost is held while a survival player of another faction is online, its holder gets
a minute in op.min (#f<N>, kept from the launch). tools/standings.py counts the week's (from its snapshot, as
it does bounties): POINTS_PER_HOUR standings points for each whole hour held, at most MAX_POINTS a week, on
top of the 100-point columns. Nothing is given: no items, no effects. A faction whose party is gone loses
what it holds (the pack, each minute) and its minutes (the hourly run, once diplomacy has removed its name;
docs/MAINTAINING.md, "The faction number in game"). The launch draws a new #epoch: a week whose snapshot has
another epoch (test play, an older world) counts every minute since; one with the same epoch counts what was
added since, so a staff penalty (minutes taken off) lowers the week's hours and never raises them.

The live map: each run also keeps a marker set ("Outposts", one marker per outpost, no holders: those change
too often to reload BlueMap for) in the Overworld map's config/bluemap/maps/*.conf, and sends `bluemap reload`
only after it wrote a changed one. It reads the outposts from the saved world, so a new spot shows on the map
the hour after. A config it can't write is warned about and left alone, with no reload.

Stdlib only plus tools/diplomacy.py, drops.py, map_border.py and saved_world.py, and Python 3.10 or newer, so
the VPS runs it straight from the checkout.
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import clips
import diplomacy
import drops
import map_border
import rcon as server
import saved_world
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, refuse, say, text
from events import ARENA_TAG, STATE
from repo import Repo

DATAPACK = "monkey-outposts"
FN = f"data/{NS}/function/outposts"
STORE = f"{NS}:outposts"
OBJ = "op"                  # #ring, #auto, #busy, #sec, #seq, #epoch, #launched and the scratch values
HOLD = "op.hold"            # #o<i>: the number of the faction holding outpost i
BY = "op.by"                # #o<i>: the faction capturing it now
PROG = "op.prog"            # #o<i>: seconds it has been capturing
MINUTES = "op.min"          # #f<N>: minutes faction N has held an outpost since the launch (the points)
ID = "op.id"                # #o<i>: the spot outpost i stands on now; a label with another id is old
TRIGGER = "outposts"

# (key, name, the way from the border's centre). Outpost i is DIRECTIONS[i - 1].
DIRECTIONS = (("north", "North", (0, -1)), ("east", "East", (1, 0)), ("south", "South", (0, 1)),
              ("west", "West", (-1, 0)))
COUNT = len(DIRECTIONS)

HALF = 12                   # blocks from the middle to the square's edge: ZONE across
ZONE = 2 * HALF + 1
BELOW, ABOVE = 8, 24        # the square's height: from 8 under the ground at its middle to 24 over it
NEAR = 64                   # blocks (either way) within which its label and particles are kept up
CAPTURE_SECONDS = 60
POINTS_PER_HOUR = 1         # standings points for each whole hour held in a week
MAX_POINTS = 20             # at most this many a week, so holding never outweighs a column

CLAIM_GAP = drops.CLAIM_GAP  # chunks between a new spot and the nearest claimed chunk (as drops)
MOVE_GAP = 3                # a claim this close (chunks) moves the outpost
CANDIDATES = 4              # spots sent for each outpost; the pack takes the first that is dry land
CANDIDATE_GAP = 4           # chunks between two candidates for the same outpost
LOG_KEEP = 500              # captures kept in storage log (the oldest go): weeks of them

# What `function monkey:outposts/survey` returns, for the timer's log (meaning()).
SURVEY_CODES = {
    1: "started: checking the ground at the spots",
    10: "outposts are off (function monkey:outposts/on)",
    11: "a survey is already running",
    12: "the season hasn't launched",
    13: "already placed for this border",
    14: "the border changed since: the next run places them all again",
    15: "the season is locked",
    16: "no spots were sent",
}


def stderr(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


HELP = [
    ("status", "where each outpost is, who holds it, the settings"),
    ("release {i:1}", "frees outpost 1 (1 North, 2 East, 3 South, 4 West), announced"),
    ("off", "no captures, no hours and no new spots until on"),
    ("on", "outposts again"),
]


# ---------------------------------------------------------------- the saved world


def launched(scores: dict[str, dict[str, int]]) -> bool:
    holder, objective = LAUNCHED.split()
    return scores.get(objective, {}).get(holder, 0) >= 1


def placed(storage: dict) -> dict[int, dict]:
    """Outpost number -> its saved spot {x, z, y, name, ...}, for those that have one."""
    at = storage.get("outposts", {}).get("at", {})
    out = {}
    for i in range(1, COUNT + 1):
        spot = at.get(f"o{i}")
        if isinstance(spot, dict) and isinstance(spot.get("x"), int) and isinstance(spot.get("z"), int):
            out[i] = spot
    return out


def holders(scores: dict[str, dict[str, int]]) -> dict[int, int]:
    """Outpost number -> the faction number holding it (outposts nobody holds are left out)."""
    held = scores.get(HOLD, {})
    return {i: held[f"#o{i}"] for i in range(1, COUNT + 1) if held.get(f"#o{i}", 0) >= 1}


def settled_border(world: Path) -> map_border.Border | None:
    """The Overworld border once it has stopped moving (a border act still growing: None, wait for it)."""
    found = saved_world.border(world, saved_world.OVERWORLD)
    if found is None or found.size != found.target or found.target >= map_border.NO_BORDER:
        return None
    return map_border.Border(found.center_x, found.center_z, found.target)


# ---------------------------------------------------------------- where


def quarter(dx: float, dz: float) -> int:
    """Which outpost's quarter (1 to COUNT) a point dx, dz from the border's centre is in."""
    if abs(dz) >= abs(dx):
        return 1 if dz < 0 else 3
    return 2 if dx > 0 else 4


def candidates(border: map_border.Border, claims: set[tuple[int, int]], seed: str,
               which: list[int]) -> list[dict]:
    """Up to CANDIDATES spots for each outpost in `which`, the first of each first: [{i, x, z}], x and z a chunk's
    middle in that outpost's quarter of drops.ring(), CLAIM_GAP chunks from every claim (drops' sampler and claim
    check). The same for the same seed and world."""
    if not which:
        return []
    found: dict[int, list[tuple[int, int]]] = {i: [] for i in which}
    for chunk, x, z in drops.ring_chunks(border, random.Random(seed)):
        if all(len(v) >= CANDIDATES for v in found.values()):
            break
        i = quarter(x - border.center_x, z - border.center_z)
        if i not in found or len(found[i]) >= CANDIDATES or drops.near_claim(chunk, claims, CLAIM_GAP):
            continue
        if any(max(abs(chunk[0] - px // 16), abs(chunk[1] - pz // 16)) < CANDIDATE_GAP for px, pz in found[i]):
            continue
        found[i].append((x, z))
    out = []
    for k in range(CANDIDATES):
        out += [{"i": i, "x": spots[k][0], "z": spots[k][1]} for i, spots in sorted(found.items()) if k < len(spots)]
    return out


def to_move(spots: dict[int, dict], claims: set[tuple[int, int]]) -> list[int]:
    """The outposts that need a spot: none yet, or a claim within MOVE_GAP chunks of theirs."""
    return [i for i in range(1, COUNT + 1)
            if i not in spots or drops.near_claim((spots[i]["x"] // 16, spots[i]["z"] // 16), claims, MOVE_GAP)]


def gone_minutes(scores: dict[str, dict[str, int]], storage: dict) -> list[str]:
    """Resets for the minutes of factions whose name diplomacy has removed (the party is gone: its number is never
    given again)."""
    names = storage.get("factions", {}).get("names", {})
    return [f"scoreboard players reset {holder} {MINUTES}" for holder in sorted(scores.get(MINUTES, {}))
            if re.fullmatch(r"#f[1-9]\d*", holder) and holder[1:] not in names]


def survey(world: Path, when: dt.datetime, scores: dict[str, dict[str, int]], spots: dict[int, dict]
           ) -> tuple[list[str], str]:
    """The survey's one RCON command for now (it carries its spots, so a survey already running keeps its own),
    and why there is none ("" when there is)."""
    if scores.get(STATE, {}).get("#season_locked", 0) == 1:
        return [], "the season is locked"
    border = settled_border(world)
    if border is None:
        return [], "no Overworld border saved, or it is still moving"
    size = round(border.size)
    claims = drops.claimed_chunks(world)
    fresh = scores.get(OBJ, {}).get("#ring", 0) != size
    which = list(range(1, COUNT + 1)) if fresh else to_move(spots, claims)
    if not which:
        return [], "every outpost has its spot"
    # Seeded by the border and the hour, so a retry for an outpost with no dry land tries new spots.
    found = candidates(border, claims, f"outposts {size} {when.astimezone(server.UTC):%Y%m%d%H}", which)
    while found:
        listed = ",".join(f"{{i:{c['i']},x:{c['x']},z:{c['z']}}}" for c in found)
        command = f"function {NS}:outposts/survey {{ring:{size},fresh:{int(fresh)},cands:[{listed}]}}"
        if len(command.encode()) <= server.LIMIT:
            return [command], ""
        found = found[:-1]   # the last candidates are the least needed
    return [], "no spot in the ring is far enough from every claim"


@dataclass
class Run:
    """One run's reading of the saved world: what to send and the map configs to write, read once."""
    commands: list[str] = field(default_factory=list)
    why: str = ""
    maps: list[tuple[Path, str]] = field(default_factory=list)
    spots: dict[int, dict] = field(default_factory=dict)
    scores: dict[str, dict[str, int]] = field(default_factory=dict)
    storage: dict = field(default_factory=dict)


def read_run(world: Path, when: dt.datetime, warn=stderr) -> Run:
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    storage = diplomacy.saved_storage(world)
    spots = placed(storage)
    run = Run(maps=map_changes(world, spots, warn), spots=spots, scores=scores, storage=storage)
    if not launched(scores):
        run.why = "the season hasn't launched"
        return run
    run.commands, run.why = survey(world, when, scores, spots)
    run.commands = gone_minutes(scores, storage) + run.commands
    return run


def plan(world: Path, when: dt.datetime) -> tuple[list[str], str]:
    """The RCON commands for now apart from the map's reload, and why there is no survey ("" when there is)."""
    run = read_run(world, when)
    return run.commands, run.why


# ---------------------------------------------------------------- the live map


BEGIN = "  # Monkey SMP outposts: tools/outposts.py writes this marker set from here to its end line; edit it there."
END = "  # Monkey SMP outposts: the end of the marker set."
MARKER_SETS = re.compile(r"^marker-sets:\s*\{\s*$")


def marker_lines(spots: dict[int, dict]) -> list[str]:
    out = [BEGIN, "  outposts: {", '    label: "Outposts"', "    toggleable: true", "    default-hidden: false",
           "    sorting: 0", "    markers: {"]
    for i, spot in sorted(spots.items()):
        key, name, _ = DIRECTIONS[i - 1]
        y = spot.get("y") if isinstance(spot.get("y"), int) else 64
        out += [f"      outpost-{key}: {{", '        type: "poi"', f'        label: "{name} outpost"',
                f'        detail: "{name} outpost: hold it with your faction for standings points. In game: '
                '/trigger outposts"',
                f"        position: {{ x: {spot['x']}, y: {y}, z: {spot['z']} }}", "        max-distance: 100000",
                "      }"]
    return out + ["    }", "  }", END]


def with_markers(conf: str, spots: dict[int, dict]) -> str:
    """A map config with its outposts marker set in step with `spots` (none: the set is taken out)."""
    lines_ = conf.split("\n")
    if BEGIN in lines_:
        start = lines_.index(BEGIN)
        if END not in lines_[start:]:
            raise ValueError("the outposts marker set has no end line: fix it by hand")
        lines_ = lines_[:start] + lines_[lines_.index(END, start) + 1:]
    at = next((n for n, line in enumerate(lines_) if MARKER_SETS.match(line)), None)
    if at is None:
        raise ValueError("no `marker-sets: {` line as BlueMap writes it")
    if spots:
        lines_ = lines_[:at + 1] + marker_lines(spots) + lines_[at + 1:]
    return "\n".join(lines_)


def map_changes(world: Path, spots: dict[int, dict], warn=stderr) -> list[tuple[Path, str]]:
    """(config, its new text) for each of this world's Overworld maps whose marker set is out of step. One that
    can't be written is warned about and left out, so nothing reloads BlueMap for it every hour."""
    server_dir = world.parent
    out = []
    for conf in sorted((server_dir / map_border.MAPS).glob("*.conf")):
        text_ = conf.read_text(encoding="utf-8")
        found = map_border.settings(text_)
        if found.get("dimension") != saved_world.OVERWORLD or found.get("world") != world.name:
            continue
        try:
            fitted = with_markers(text_, spots)
        except ValueError as e:
            warn(f"{conf}: {e}; the map shows no outposts")
            continue
        if fitted == text_:
            continue
        if not os.access(conf, os.W_OK):
            warn(f"{conf} can't be written: the map's outposts are out of date")
            continue
        out.append((conf, fitted))
    return out


# ---------------------------------------------------------------- the timer's commands


def commands(world: Path, when: dt.datetime) -> list[str]:
    """What deploy/monkey-outposts.sh sends: gone factions' minutes reset, a survey when an outpost needs a spot,
    and `bluemap reload` when a map's marker set is out of step (and its config can be written)."""
    run = read_run(world, when)
    return run.commands + (["bluemap reload"] if run.maps else [])


def meaning(command: str, answer: str) -> str:
    """The timer's log line for one command's answer: the survey's return code in words."""
    if command.startswith(f"function {NS}:outposts/survey"):
        m = re.search(r" returned (\d+)$", answer)
        said = SURVEY_CODES.get(int(m[1]), answer) if m else answer or "ok"
        return f"function {NS}:outposts/survey: {said}"
    return f"{command}: {answer or 'ok'}"


def send(rcon, world: Path, when: dt.datetime, log=print) -> int:
    """Reads the world once, writes the map's marker set when it is out of step, then sends the commands (none:
    nothing is logged; a server that isn't running is skipped, and loads the map's markers when it starts).
    `bluemap reload` goes only after a config was written."""
    run = read_run(world, when, warn=lambda msg: log(f"map: {msg}"))
    written = False
    for conf, fitted in run.maps:
        try:
            conf.write_text(fitted, encoding="utf-8", newline="")   # in place: keeps the owner
            log(f"map: outposts marker set written to {conf.name}")
            written = True
        except OSError as e:
            log(f"map: could not write {conf}: {e}; no reload")
    out = run.commands + (["bluemap reload"] if written else [])
    if not out:
        return 0
    return server.send_if_running(rcon, out, log, describe=meaning, stop=True)


def status(world: Path, when: dt.datetime) -> int:
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    storage = diplomacy.saved_storage(world)
    names = diplomacy.post_names(storage)
    found = saved_world.border(world, saved_world.OVERWORLD)
    print(f"launched: {'yes' if launched(scores) else 'no'}; placed for a border of "
          f"{scores.get(OBJ, {}).get('#ring', 0) or 'none yet'}")
    if found:
        moving = f", moving to {found.target:g}" if found.size != found.target else ""
        print(f"Overworld border {found.size:g} wide at {found.center_x:g}, {found.center_z:g}{moving}")
        if not moving and found.target < map_border.NO_BORDER:
            inner, outer = drops.ring(map_border.Border(found.center_x, found.center_z, found.target))
            print(f"outposts go between {inner:g} and {outer:g} blocks from its centre, either axis")
    claims = drops.claimed_chunks(world)
    held = holders(scores)
    for i, spot in sorted(placed(storage).items()):
        h = held.get(i)
        who = f"held by {names.get(h, f'faction {h}')}" if h else "held by nobody"
        close = " (a claim is too close: it moves)" if i in to_move({i: spot}, claims) else ""
        print(f"  {DIRECTIONS[i - 1][1]}: {spot['x']} {spot.get('y', '?')} {spot['z']}, {who}{close}")
    run = read_run(world, when)
    out, why = run.commands + (["bluemap reload"] if run.maps else []), run.why
    print("the timer would send:" if out else f"the timer would send nothing: {why}")
    if out and why:
        print(f"  (no survey: {why})")
    for command in out:
        print(f"  {command}")
    return 0


# ---------------------------------------------------------------- standings and the recap


def epoch(scores: dict[str, dict[str, int]]) -> int:
    """The launch's number (drawn once by the pack's launch): 0 before the launch."""
    return scores.get(OBJ, {}).get("#epoch", 0)


def baseline(scores: dict[str, dict[str, int]]) -> dict:
    """What a standings week starts from (in its snapshot): the launch's epoch, every faction's minutes held, and
    the capture log's newest number."""
    return {"epoch": epoch(scores),
            "minutes": dict(sorted((h, v) for h, v in scores.get(MINUTES, {}).items() if h.startswith("#f"))),
            "seq": scores.get(OBJ, {}).get("#seq", 0)}


def hours(scores: dict[str, dict[str, int]], base: dict | None, number: int | None) -> int:
    """Whole hours faction `number` held outposts since the week's snapshot. A snapshot from another epoch (before
    the launch, or another world) counts from nothing. In the same epoch a count lower than at the start is a
    staff penalty: the week has no hours (it never adds any)."""
    if number is None:
        return 0
    base = base or {}
    now = scores.get(MINUTES, {}).get(f"#f{number}", 0)
    same = epoch(scores) != 0 and base.get("epoch") == epoch(scores)
    then = (base.get("minutes") or {}).get(f"#f{number}", 0) if same else 0
    return max(0, now - then) // 60


def points(held: int) -> int:
    """Standings points for `held` hours in a week."""
    return min(MAX_POINTS, POINTS_PER_HOUR * max(0, held))


def captures(storage: dict, base: dict | None) -> list[tuple[str, str]]:
    """The captures logged since a week's baseline() (`base`), oldest first: (the outpost's name, the faction's).
    A baseline from another epoch (before the launch, another world): all of the log."""
    mine = storage.get("outposts", {})
    log = [e for e in mine.get("log", []) if isinstance(e, dict) and e.get("kind") == "capture"]
    base = base or {}
    since = base.get("seq", 0) if base.get("epoch") and base.get("epoch") == mine.get("epoch") else 0
    known = diplomacy.post_names(storage)
    out = []
    for e in sorted(log, key=lambda e: int(e.get("n", 0))):
        o, f = int(e.get("o", 0)), int(e.get("f", 0))
        if int(e.get("n", 0)) > since and 1 <= o <= COUNT:
            out.append((DIRECTIONS[o - 1][1], known.get(f, f"faction {f}")))
    return out


def recap_lines(rows: list[dict], storage: dict, base: dict | None) -> list[str]:
    """An "outposts this week" section for the Sunday recap: [] for a week nobody held or took one. `rows` are a
    closed week's (each with "outposts", hours held); `base` its snapshot's baseline() ("outposts")."""
    held = sorted(((r.get("outposts", 0), r["name"]) for r in rows if r.get("outposts", 0) > 0),
                  key=lambda t: (-t[0], t[1].casefold()))
    taken = captures(storage, base)
    if not held and not taken:
        return []
    out = []
    if held:
        best = ", ".join(f"{diplomacy.discord_name(name)} {h} h" for h, name in held[:3])
        out.append(f"**Outposts:** held longest by {best}.")
    if taken:
        out.append(f"{len(taken)} capture{'s' if len(taken) != 1 else ''} this week; last, "
                   f"{diplomacy.discord_name(taken[-1][1])} took the {taken[-1][0]} outpost.")
    return out


# ---------------------------------------------------------------- the data pack


HEAD = {"text": "Outposts: ", "color": "gold", "bold": True}
LABEL = "op.label"


def zone(scores: bool = True) -> str:
    """The players inside an outpost's square, from the macro arguments zx, zy, zz (its corner)."""
    faction = f",scores={{{diplomacy.FACTION}=1..}}" if scores else ""
    return (f"@e[type=minecraft:player,gamemode=survival,tag=!{ARENA_TAG},x=$(zx),y=$(zy),z=$(zz),"
            f"dx={ZONE - 1},dy={BELOW + ABOVE},dz={ZONE - 1}{faction}]")


def at(i: int, key: str, color: str = "aqua") -> dict:
    return {"nbt": f"at.o{i}.{key}", "storage": STORE, "color": color}


def gray(s: str) -> dict:
    return {"text": s, "color": "gray"}


def held_by(var: str) -> dict:
    return diplomacy.faction(var)


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP outposts (generated by tools/outposts.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:outposts/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:outposts/tick")
    f[f"data/{NS}/tags/block/outposts/ground.json"] = json.dumps({"values": drops.GROUND}, indent=2)
    locked = f"#season_locked {STATE} matches 1"

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/outposts.py. Scores and storage are kept across restarts.",
        *(f"scoreboard objectives add {o} dummy" for o in (OBJ, HOLD, BY, PROG, MINUTES, ID)),
        f"scoreboard objectives add {TRIGGER} trigger",
        f"execute unless score #auto {OBJ} matches 0.. run scoreboard players set #auto {OBJ} 1",
        f"execute unless score #busy {OBJ} matches 0.. run scoreboard players set #busy {OBJ} 0",
        f"execute unless data storage {STORE} log run data modify storage {STORE} log set value []",
        f"scoreboard players set #60 {OBJ} 60",
        f"schedule function {NS}:outposts/second 20t replace",
        "# Checking the ground when the server stopped: check again (a schedule may not outlast a restart).",
        f"execute if score #busy {OBJ} matches 1 run schedule function {NS}:outposts/check 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        f"execute as @a[scores={{{TRIGGER}=1..}}] run function {NS}:outposts/use",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:outposts/second 20t replace",
        f"scoreboard players enable @a {TRIGGER}",
        "# A label left from an earlier spot goes once its chunk is loaded.",
        *(f"execute as @e[type=minecraft:text_display,tag=op.l{i}] unless score @s {ID} = #o{i} {ID} run kill @s"
          for i in range(1, COUNT + 1)),
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        f"execute unless score #launched {OBJ} matches 1 run function {NS}:outposts/launch",
        f"execute if score {locked} run return 0",
        f"execute unless score #auto {OBJ} matches 1 run return 0",
        *(f"execute if data storage {STORE} at.o{i} run function {NS}:outposts/o/{i}/second with storage {STORE} "
          f"at.o{i}" for i in range(1, COUNT + 1)),
        f"scoreboard players add #sec {OBJ} 1",
        f"execute if score #sec {OBJ} matches 60.. run function {NS}:outposts/minute",
    )
    f[f"{FN}/launch.mcfunction"] = lines(
        "# Once, the first second after the launch (monkey:rules/launch sets #launched rw.day): nothing from test",
        "# play counts. The outposts go, and the timer places them anew within the hour.",
        "# Labels lose their ids too, so any left from test play go when their chunk loads. A new epoch tells",
        "# tools/standings.py that every minute from here on is new.",
        *(f"scoreboard players reset * {o}" for o in (HOLD, BY, PROG, MINUTES, ID)),
        f"execute store result score #epoch {OBJ} run random value 1..1000000000",
        f"execute store result storage {STORE} epoch int 1 run scoreboard players get #epoch {OBJ}",
        f"execute if score #busy {OBJ} matches 1 run function {NS}:outposts/unload with storage {STORE} cand",
        f"function {NS}:outposts/done",
        f"data remove storage {STORE} at",
        f"data modify storage {STORE} log set value []",
        f"scoreboard players set #ring {OBJ} 0",
        f"scoreboard players set #seq {OBJ} 0",
        f"scoreboard players set #launched {OBJ} 1",
    )
    f[f"{FN}/minute.mcfunction"] = lines(
        f"scoreboard players set #sec {OBJ} 0",
        "# A gone faction's minutes are reset by the hourly timer (tools/outposts.py gone_minutes).",
        *(f"execute if score #o{i} {HOLD} matches 1.. run function {NS}:outposts/o/{i}/minute"
          for i in range(1, COUNT + 1)),
    )
    f[f"{FN}/log.mcfunction"] = lines(
        "# Macro {o, f}: a capture, numbered, for the Sunday recap (tools/outposts.py captures).",
        f"scoreboard players add #seq {OBJ} 1",
        f'$data modify storage {STORE} log append value {{kind:"capture",o:$(o),f:$(f)}}',
        f"execute store result storage {STORE} log[-1].n int 1 run scoreboard players get #seq {OBJ}",
        f"execute if data storage {STORE} log[{LOG_KEEP}] run data remove storage {STORE} log[0]",
    )

    # ------------------------------------------------ each outpost
    for i in range(1, COUNT + 1):
        f.update(outpost_files(i))

    # ------------------------------------------------ finding the spots
    f[f"{FN}/survey.mcfunction"] = lines(
        "# deploy/monkey-outposts.sh: macro {ring, fresh, cands}, cands the spots ([{i, x, z}], the first for each",
        "# outpost first). fresh 1: a new border, so every outpost starts over; 0: only the outposts named get a",
        "# spot (holders keep them). Returns why it didn't start (SURVEY_CODES); a running survey keeps its spots.",
        f"execute unless score #auto {OBJ} matches 1 run return 10",
        f"execute if score #busy {OBJ} matches 1 run return 11",
        f"execute unless score {LAUNCHED} matches 1 run return 12",
        f"execute if score {locked} run return 15",
        f"$scoreboard players set #fresh {OBJ} $(fresh)",
        f"$scoreboard players set #want {OBJ} $(ring)",
        f"execute if score #fresh {OBJ} matches 1 if score #want {OBJ} = #ring {OBJ} run return 13",
        f"execute if score #fresh {OBJ} matches 0 unless score #want {OBJ} = #ring {OBJ} run return 14",
        f"$data modify storage {STORE} cands set value $(cands)",
        f"execute unless data storage {STORE} cands[0] run return 16",
        f"scoreboard players set #busy {OBJ} 1",
        *(f"scoreboard players set #d{i} {OBJ} 0" for i in range(1, COUNT + 1)),
        f"execute if score #fresh {OBJ} matches 1 run function {NS}:outposts/fresh",
        f"function {NS}:outposts/next",
        "return 1",
    )
    f[f"{FN}/fresh.mcfunction"] = lines(
        "# A new border ring: every outpost goes, and its holder with it (hours already earned stay).",
        f"execute if score #ring {OBJ} matches 1.. run tellraw @a " + text(
            "", HEAD, {"text": "the border has moved, and the outposts move out to the new land. Their spots "
                               "follow in chat.", "color": "yellow"}),
        f"data remove storage {STORE} at",
        *(c for i in range(1, COUNT + 1) for c in (f"scoreboard players reset #o{i} {HOLD}",
                                                    f"scoreboard players reset #o{i} {BY}",
                                                    f"scoreboard players reset #o{i} {PROG}",
                                                    f"scoreboard players reset #o{i} {ID}")),
        f"scoreboard players operation #ring {OBJ} = #want {OBJ}",
    )
    f[f"{FN}/next.mcfunction"] = lines(
        f"execute unless data storage {STORE} cands[0] run return run function {NS}:outposts/done",
        f"data modify storage {STORE} cand set from storage {STORE} cands[0]",
        f"data remove storage {STORE} cands[0]",
        f"function {NS}:outposts/pick with storage {STORE} cand",
    )
    # forceload works in the dimension it runs in: pinned to the Overworld, where the outposts are.
    overworld = f"execute in {saved_world.OVERWORLD}"
    f[f"{FN}/stopped.mcfunction"] = lines(
        "# 1 when a survey must stop: outposts turned off, or the season locked.",
        f"execute unless score #auto {OBJ} matches 1 run return 1",
        f"execute if score {locked} run return 1",
        "return 0",
    )
    f[f"{FN}/abort.mcfunction"] = lines(
        "# Stopped mid-survey: the chunk being checked is let go, nothing is placed or announced.",
        f"function {NS}:outposts/unload with storage {STORE} cand",
        f"function {NS}:outposts/done",
    )
    f[f"{FN}/pick.mcfunction"] = lines(
        "# Macro cand {i, x, z}: an outpost that found its spot this survey skips the rest of its candidates.",
        f"execute if function {NS}:outposts/stopped run return run function {NS}:outposts/done",
        f"$execute if score #d$(i) {OBJ} matches 1 run return run function {NS}:outposts/next",
        f"scoreboard players set #wait {OBJ} 0",
        f"${overworld} run forceload add $(x) $(z)",
        f"schedule function {NS}:outposts/check 20t replace",
    )
    f[f"{FN}/check.mcfunction"] = lines(
        f"execute unless score #busy {OBJ} matches 1 run return 0",
        f"execute if function {NS}:outposts/stopped run return run function {NS}:outposts/abort",
        f"function {NS}:outposts/check_at with storage {STORE} cand",
    )
    f[f"{FN}/check_at.mcfunction"] = lines(
        f"${overworld} unless loaded $(x) 0 $(z) run return run function {NS}:outposts/wait",
        f"${overworld} positioned $(x) 0 $(z) align xz positioned over motion_blocking_no_leaves if block ~ ~-1 ~ "
        f"#{NS}:outposts/ground run return run function {NS}:outposts/found",
        "# Water, a build or anything else: the next candidate.",
        f"function {NS}:outposts/skip",
    )
    f[f"{FN}/wait.mcfunction"] = lines(
        f"scoreboard players add #wait {OBJ} 1",
        f"execute if score #wait {OBJ} matches ..10 run return run schedule function {NS}:outposts/check 20t replace",
        f"function {NS}:outposts/skip",
    )
    f[f"{FN}/skip.mcfunction"] = lines(
        f"function {NS}:outposts/unload with storage {STORE} cand",
        f"function {NS}:outposts/next",
    )
    f[f"{FN}/unload.mcfunction"] = lines(f"${overworld} run forceload remove $(x) $(z)")
    f[f"{FN}/found.mcfunction"] = lines(
        "# Run at the candidate's surface: it is dry land, so the outpost stands here.",
        "summon minecraft:marker ~ ~ ~ {Tags:[\"op.y\"]}",
        f"execute store result storage {STORE} cand.y int 1 run data get entity @e[type=minecraft:marker,"
        "tag=op.y,limit=1] Pos[1]",
        "kill @e[type=minecraft:marker,tag=op.y]",
        "# The square's corner (zx, zy, zz), the near box's (nx, nz), the far corner (ex, ez) and the label's",
        "# height (ly).",
        *(f"execute store result score #{k} {OBJ} run data get storage {STORE} cand.{k}" for k in ("x", "y", "z")),
        *(c for k in ("x", "z") for c in (
            f"execute store result storage {STORE} cand.z{k} int 1 run scoreboard players remove #{k} {OBJ} {HALF}",
            f"execute store result storage {STORE} cand.e{k} int 1 run scoreboard players add #{k} {OBJ} {ZONE - 1}",
            f"execute store result storage {STORE} cand.n{k} int 1 run scoreboard players remove #{k} {OBJ} "
            f"{ZONE + NEAR - HALF - 1}")),
        f"execute store result storage {STORE} cand.zy int 1 run scoreboard players remove #y {OBJ} {BELOW}",
        f"execute store result storage {STORE} cand.ly int 1 run scoreboard players add #y {OBJ} {BELOW + 3}",
        f"function {NS}:outposts/settle with storage {STORE} cand",
        f"function {NS}:outposts/skip",
    )
    f[f"{FN}/settle.mcfunction"] = lines(f"$function {NS}:outposts/o/$(i)/settle")
    f[f"{FN}/done.mcfunction"] = lines(
        f"scoreboard players set #busy {OBJ} 0",
        f"data remove storage {STORE} cand",
        f"data remove storage {STORE} cands",
    )
    f[f"{FN}/placed.mcfunction"] = lines(
        "# Macro at.o<i> {name, x, z}.",
        "$tellraw @a " + text("", HEAD, {"text": "the $(name) outpost stands at $(x), $(z). Hold it with your "
                                                 "faction for standings points: /trigger outposts", "color": "yellow"}),
    )
    f[f"{FN}/moved.mcfunction"] = lines(
        "$tellraw @a " + text("", HEAD, {"text": "a claim came too close, so the $(name) outpost moved to $(x), "
                                                 "$(z). Whoever held it still does.", "color": "yellow"}),
    )

    # ------------------------------------------------ /trigger outposts
    f[f"{FN}/use.mcfunction"] = lines(
        "# Runs as a player who used /trigger outposts.",
        f"scoreboard players set @s {TRIGGER} 0",
        f"scoreboard players enable @s {TRIGGER}",
        "tellraw @s " + text({"text": "Outposts", "color": "gold", "bold": True}),
        "tellraw @s " + text(gray(
            f"Stand in an outpost's square (about {ZONE} blocks across) with your faction and nobody from another "
            f"for {CAPTURE_SECONDS} seconds to take it. Each hour your faction holds one while a player of another "
            f"faction is online is +{POINTS_PER_HOUR} standings point this week (at most {MAX_POINTS}). Claims and "
            "the rules stay as they are.")),
        *(f"execute if data storage {STORE} at.o{i} run function {NS}:outposts/o/{i}/line"
          for i in range(1, COUNT + 1)),
        f"execute unless data storage {STORE} at.o1 unless data storage {STORE} at.o2 unless data storage {STORE} "
        f"at.o3 unless data storage {STORE} at.o4 run tellraw @s " + text(gray(
            "No outposts yet: they are placed within the hour after the launch, and again after each border act.")),
        f"execute unless score @s {diplomacy.FACTION} matches 1.. run return run tellraw @s " + text(gray(
            "You're in no faction the server knows yet, so you can't take one. Make or join a party (/oparties); "
            "the server picks it up within the hour.")),
        f"execute store result storage {STORE} me.f int 1 run scoreboard players get @s {diplomacy.FACTION}",
        f"function {NS}:outposts/mine with storage {STORE} me",
    )
    f[f"{FN}/mine.mcfunction"] = lines(
        "# Macro {f}: the player's faction's hours held this season.",
        f"scoreboard players set #h {OBJ} 0",
        f"$scoreboard players operation #h {OBJ} = #f$(f) {MINUTES}",
        f"scoreboard players operation #h {OBJ} /= #60 {OBJ}",
        "tellraw @s " + text("", gray("Your faction has held outposts for "),
                             {"score": {"name": "#h", "objective": OBJ}, "color": "white"},
                             gray(" hours this season (the hours that count).")),
    )

    # ------------------------------------------------ staff
    f[f"{FN}/status.mcfunction"] = lines(
        say({"text": "Outposts: ", "color": "gold"}, gray("on "), {"score": {"name": "#auto", "objective": OBJ}},
            gray(", checking the ground "), {"score": {"name": "#busy", "objective": OBJ}},
            gray(", placed for a border of "), {"score": {"name": "#ring", "objective": OBJ}}),
        *(say(gray(f" {i}. {DIRECTIONS[i - 1][1]}: "), at(i, "x"), gray(" "), at(i, "y"), gray(" "), at(i, "z"),
              gray(", held by faction "), {"score": {"name": f"#o{i}", "objective": HOLD}},
              gray(", capturing "), {"score": {"name": f"#o{i}", "objective": BY}},
              gray(" for "), {"score": {"name": f"#o{i}", "objective": PROG}}, gray(" s"))
          for i in range(1, COUNT + 1)),
    )
    f[f"{FN}/release.mcfunction"] = lines(
        "# Staff, macro {i:1}: outpost i is held by nobody (say when it was taken against the rules).",
        f"$scoreboard players set #v {OBJ} $(i)",
        f"execute unless score #v {OBJ} matches 1..{COUNT} run " + refuse(
            "Outposts are 1 North, 2 East, 3 South and 4 West: release {i:1}"),
        f"$function {NS}:outposts/o/$(i)/release",
        "$tellraw @a " + text("", HEAD, {"text": "staff freed outpost $(i): nobody holds it now.", "color": "yellow"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 0",
        say({"text": "Outposts are off: no captures, no hours and no new spots until ", "color": "yellow"},
            {"text": f"/function {NS}:outposts/on", "color": "aqua"}),
    )
    f[f"{FN}/on.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 1",
        say({"text": "Outposts are on.", "color": "green"}),
    )
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def outpost_files(i: int) -> dict[str, str]:
    """Outpost i's own functions (its scores are #o<i>; its spot is storage at.o<i>)."""
    f: dict[str, str] = {}
    key, name, _ = DIRECTIONS[i - 1]
    o = f"{FN}/o/{i}"
    call = f"{NS}:outposts/o/{i}"
    me = f"#o{i}"
    label_tag = f"op.l{i}"
    labels = f"@e[type=minecraft:text_display,tag={label_tag}]"
    where = [at(i, "x"), {"text": ", ", "color": "aqua"}, at(i, "z")]

    f[f"{o}/second.mcfunction"] = lines(
        f"# Macro at.o{i}: every second. Keeps its label up while anyone is near, then counts who is inside.",
        f"$execute if entity @a[x=$(nx),y=-64,z=$(nz),dx={2 * NEAR},dy=384,dz={2 * NEAR}] run "
        f"function {call}/near with storage {STORE} at.o{i}",
        f"$execute store result score #n {OBJ} if entity {zone()}",
        "# Nobody of a faction inside: an attempt ends.",
        f"execute if score #n {OBJ} matches 0 run return run scoreboard players set {me} {PROG} 0",
        f"$execute as {zone()[:-1]},limit=1,sort=random] run scoreboard players operation #c {OBJ} = @s "
        f"{diplomacy.FACTION}",
        f"scoreboard players set #mixed {OBJ} 0",
        f"$execute as {zone()} unless score @s {diplomacy.FACTION} = #c {OBJ} run scoreboard players set #mixed "
        f"{OBJ} 1",
        "# Two factions inside: contested, and the count waits.",
        f"$execute if score #mixed {OBJ} matches 1 run return run title {zone(False)} actionbar " + text(
            {"text": f"The {name} outpost is contested", "color": "red"}),
        f"$execute if score #c {OBJ} = {me} {HOLD} run title {zone()} actionbar " + text(
            {"text": f"Your faction holds the {name} outpost", "color": "green"}),
        f"execute if score #c {OBJ} = {me} {HOLD} run return run scoreboard players set {me} {PROG} 0",
        f"execute unless score #c {OBJ} = {me} {BY} run scoreboard players set {me} {PROG} 0",
        f"scoreboard players operation {me} {BY} = #c {OBJ}",
        f"scoreboard players add {me} {PROG} 1",
        f"execute if score {me} {PROG} matches 1 run function {call}/attacked",
        f"$title {zone()} actionbar " + text(
            "", {"text": f"Taking the {name} outpost: ", "color": "yellow"},
            {"score": {"name": me, "objective": PROG}, "color": "white"},
            {"text": f" of {CAPTURE_SECONDS} seconds", "color": "yellow"}),
        f"execute if score {me} {PROG} matches {CAPTURE_SECONDS}.. run function {call}/captured",
    )
    f[f"{o}/near.mcfunction"] = lines(
        f"# Macro at.o{i}, while a player is within {NEAR} blocks: its chunk is loaded, so its label is too.",
        "# A label from an earlier spot goes first, so the one kept below is never it.",
        f"execute as {labels} unless score @s {ID} = {me} {ID} run kill @s",
        f"$execute unless entity @e[type=minecraft:text_display,tag={label_tag},x=$(zx),y=$(zy),z=$(zz),"
        f"dx={ZONE - 1},dy={BELOW + ABOVE},dz={ZONE - 1}] positioned $(x) $(ly) $(z) align xz run summon "
        f"minecraft:text_display ~0.5 ~ ~0.5 {{Tags:[\"{LABEL}\",\"{label_tag}\",\"op.new\"],billboard:\"center\","
        "view_range:2.0f}",
        f"scoreboard players operation @e[type=minecraft:text_display,tag=op.new] {ID} = {me} {ID}",
        f"execute as @e[type=minecraft:text_display,tag=op.new] run data modify entity @s text set from storage "
        f"{STORE} label.o{i}",
        "tag @e[type=minecraft:text_display,tag=op.new] remove op.new",
        "# Entities load after their chunk: one summoned before the old one loaded is one too many. Keep one.",
        f"execute store result score #lc {OBJ} if entity {labels}",
        f"execute if score #lc {OBJ} matches 2.. run function {call}/one_label",
        "# Its square's corners, and a column at its middle while someone holds it.",
        *(f"$execute positioned $({cx}) 0 $({cz}) positioned over motion_blocking_no_leaves run particle "
          "minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3" for cx, cz in (("zx", "zz"), ("ex", "zz"), ("zx", "ez"),
                                                                ("ex", "ez"))),
        f"$execute if score {me} {HOLD} matches 1.. positioned $(x) $(ly) $(z) align xz run particle "
        "minecraft:end_rod ~0.5 ~ ~0.5 0.1 2 0.1 0.01 6",
    )
    f[f"{o}/one_label.mcfunction"] = lines(
        f"tag @e[type=minecraft:text_display,tag={label_tag},limit=1] add op.keep",
        f"kill @e[type=minecraft:text_display,tag={label_tag},tag=!op.keep]",
        "tag @e[type=minecraft:text_display,tag=op.keep] remove op.keep",
    )
    f[f"{o}/label.mcfunction"] = lines(
        f"# The text over outpost {i}: its name and who holds it.",
        f"data modify storage {STORE} label.o{i} set value " + snbt_label(name),
        f"execute unless score {me} {HOLD} matches 1.. run return 0",
        f"execute store result storage {STORE} tmp.h int 1 run scoreboard players get {me} {HOLD}",
        f"function {call}/label_holder with storage {STORE} tmp",
    )
    f[f"{o}/label_holder.mcfunction"] = lines(
        f"$data modify storage {STORE} label.o{i}.extra[2] set from storage {diplomacy.FACTIONS} names.f$(h)",
    )
    f[f"{o}/settle.mcfunction"] = lines(
        f"# From storage cand (found dry land): outpost {i} stands there now.",
        f"scoreboard players set #moved {OBJ} 0",
        f"execute if data storage {STORE} at.o{i} run scoreboard players set #moved {OBJ} 1",
        f"data modify storage {STORE} at.o{i} set from storage {STORE} cand",
        f'data modify storage {STORE} at.o{i}.name set value "{name}"',
        f"scoreboard players add #next {ID} 1",
        f"scoreboard players operation {me} {ID} = #next {ID}",
        f"scoreboard players set #d{i} {OBJ} 1",
        f"scoreboard players set {me} {PROG} 0",
        f"scoreboard players reset {me} {BY}",
        f"function {call}/label",
        "# The chunk is force-loaded while it is checked: put the label up now.",
        f"function {call}/near with storage {STORE} at.o{i}",
        f"execute if score #moved {OBJ} matches 1 run function {NS}:outposts/moved with storage {STORE} at.o{i}",
        f"execute if score #moved {OBJ} matches 0 run function {NS}:outposts/placed with storage {STORE} at.o{i}",
    )
    f[f"{o}/attacked.mcfunction"] = lines(
        "# An attempt has started: the holder's members are told.",
        f"execute unless score {me} {HOLD} matches 1.. run return 0",
        f"execute store result storage {STORE} tmp.h int 1 run scoreboard players get {me} {HOLD}",
        f"execute store result storage {STORE} tmp.c int 1 run scoreboard players get #c {OBJ}",
        f"function {call}/alert with storage {STORE} tmp",
    )
    f[f"{o}/alert.mcfunction"] = lines(
        f"$tellraw @a[scores={{{diplomacy.FACTION}=$(h)}}] " + text(
            "", HEAD, held_by("c"), {"text": f" are taking your {name} outpost at ", "color": "red"}, *where,
            {"text": f". {CAPTURE_SECONDS} seconds alone inside and it's theirs.", "color": "red"}),
        f"$execute as @a[scores={{{diplomacy.FACTION}=$(h)}}] at @s run playsound minecraft:block.bell.use master @s "
        "~ ~ ~ 0.8 0.8",
    )
    f[f"{o}/captured.mcfunction"] = lines(
        f"scoreboard players operation {me} {HOLD} = #c {OBJ}",
        f"scoreboard players set {me} {PROG} 0",
        f"scoreboard players reset {me} {BY}",
        f"function {call}/label",
        f"execute as {labels} run data modify entity @s text set from storage {STORE} label.o{i}",
        f"execute store result storage {STORE} tmp.c int 1 run scoreboard players get #c {OBJ}",
        f"function {call}/taken with storage {STORE} tmp",
        "# A clip marker as the taker nearest the outpost's label (in the middle; no capture while contested).",
        f"execute at {labels[:-1]},limit=1] as @a[distance=..{ZONE},limit=1,sort=nearest,"
        f"scores={{{diplomacy.FACTION}=1..}}] at @s run " + clips.mark("outpost", f"The {name} outpost is taken"),
        "execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.4 1.4",
    )
    f[f"{o}/taken.mcfunction"] = lines(
        "$tellraw @a " + text("", HEAD, held_by("c"), {"text": f" took the {name} outpost at ", "color": "yellow"},
                              *where, {"text": ".", "color": "yellow"}),
        f"$function {NS}:outposts/log {{o:{i},f:$(c)}}",
    )
    f[f"{o}/minute.mcfunction"] = lines(
        f"execute store result storage {STORE} tmp.h int 1 run scoreboard players get {me} {HOLD}",
        f"function {call}/credit with storage {STORE} tmp",
        "# The holder's name as the board run last wrote it (a renamed party shows its new name).",
        f"function {call}/label",
        f"execute as {labels} run data modify entity @s text set from storage {STORE} label.o{i}",
    )
    f[f"{o}/credit.mcfunction"] = lines(
        "# Macro {h}: a minute held counts while a survival player of another faction is online (someone who",
        "# could take it back). A faction that is gone holds nothing.",
        f"$execute unless data storage {diplomacy.FACTIONS} names.f$(h) run return run function {call}/gone",
        f"$execute store result score #mine {OBJ} if entity @a[gamemode=survival,scores={{{diplomacy.FACTION}=$(h)}}]",
        f"execute store result score #all {OBJ} if entity @a[gamemode=survival,scores={{{diplomacy.FACTION}=1..}}]",
        f"execute unless score #all {OBJ} > #mine {OBJ} run return 0",
        f"$scoreboard players add #f$(h) {MINUTES} 1",
    )
    f[f"{o}/gone.mcfunction"] = lines(
        f"function {call}/release",
        "tellraw @a " + text("", HEAD, {"text": f"the {name} outpost is free: the faction that held it is gone.",
                                        "color": "yellow"}),
    )
    f[f"{o}/release.mcfunction"] = lines(
        f"scoreboard players reset {me} {HOLD}",
        f"scoreboard players reset {me} {BY}",
        f"scoreboard players set {me} {PROG} 0",
        f"function {call}/label",
        f"execute as {labels} run data modify entity @s text set from storage {STORE} label.o{i}",
    )
    f[f"{o}/line.mcfunction"] = lines(
        f"# /trigger outposts: outpost {i}'s line.",
        f"execute unless score {me} {HOLD} matches 1.. run tellraw @s " + text(
            "", {"text": f" - {name} at ", "color": "gray"}, *where, gray(": nobody holds it")),
        f"execute if score {me} {HOLD} matches 1.. run function {call}/line_held",
        f"execute if score {me} {PROG} matches 1.. run tellraw @s " + text(gray("   someone is taking it right now")),
    )
    f[f"{o}/line_held.mcfunction"] = lines(
        f"execute store result storage {STORE} tmp.h int 1 run scoreboard players get {me} {HOLD}",
        f"function {call}/line_name with storage {STORE} tmp",
    )
    f[f"{o}/line_name.mcfunction"] = lines(
        "$tellraw @s " + text("", {"text": f" - {name} at ", "color": "gray"}, *where, gray(": "), held_by("h"),
                              gray(" hold it")),
    )
    assert key  # every direction has a key (the map's marker id)
    return f


def snbt_label(name: str) -> str:
    """The label's text before a holder is known, as SNBT: name, then "held by nobody"."""
    return (f'{{text:"",extra:[{{text:"{name} outpost\\n",color:"gold",bold:1b}},'
            '{text:"held by ",color:"gray"},{text:"nobody",color:"white"}]}')


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box.",
           say({"text": "Outpost commands (docs/ADMIN.md):", "color": "gold"})]
    for cmd, note in HELP:
        path = cmd.split(" ")[0]
        assert f"{FN}/{path}.mcfunction" in files, path
        out.append(say({"text": f" {cmd}", "color": "aqua",
                        "click_event": {"action": "suggest_command", "command": f"/function {NS}:outposts/{cmd}"}},
                       {"text": f"  {note}", "color": "dark_gray"}))
    return lines(*out)


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Outposts: their spots, the timer's commands, the data pack.")
    sub = ap.add_subparsers(dest="command", required=True)
    server.job_subcommands(sub, "sends them to the running server (deploy/monkey-outposts.sh, hourly)",
                           world=True, others=[("status", "where they are, who holds them, what the timer would do")])
    args = ap.parse_args(argv)
    if args.command == "status":
        return status(args.world, server.job_time(args))
    return server.run_job(args, lambda when: commands(args.world, when),
                          lambda rcon, when: send(rcon, args.world, when))


if __name__ == "__main__":
    sys.exit(main())
