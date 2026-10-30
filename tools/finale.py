"""The finale: on the season's last Saturday the border closes on the monument, and the faction holding it wins.

    python tools/datapacks.py                     regenerates the monkey-finale data pack (with the others)
    python tools/finale.py plan [--season N] [--world WORLD]   the stages, and the monument for this world
    python tools/finale.py result WORLD           who held the monument, their roster, and the staff commands

What players see (docs/SEASONS.md, "The finale"): at the finale's time chat says the border starts closing in 10
minutes, then in 1 minute, then now. From now it shrinks from wherever it is to FINAL_SIZE blocks across over
SHRINK_SECONDS, while its centre moves from spawn to the monument (MONUMENT_OFFSET from spawn, outside spawn's
no-PvP zone: docs/RULES.md, rules 22 and 26) a block a second each way. Then comes the last hour (HOLD_SECONDS),
a staff event (rule 41: anyone can fight anyone within EVENT_RADIUS of the monument): the border holds, and every
second each faction gets a point for each of its members standing at the monument (within RADIUS blocks of it
either way, any height, in survival, not in the event arena). 10 minutes and 1 minute before the close, chat says
so; at the close the faction with the most points holds the monument and is named the winner. A boss bar counts
down to the close all along. Claims are never touched: land outside the border is only out of reach.

Never stranded: the shrink is slow (an edge moves at most about 2.2 blocks a second, under half walking pace), every
player within EDGE_MARGIN blocks of the edge or past it is warned on screen every 5 seconds with the monument's
coordinates, and from the shrink on anyone outside the border (a player who logs in out there, say) is moved
to a safe spot inside it. The border never goes below FINAL_SIZE, which is never below MIN_SIZE, and a border
already that small is left alone. Only the Overworld's border moves: the Nether's stays, and a portal never
puts a player outside the Overworld's (the game keeps a portal's exit inside the border).

The result is read from the scores: #f<N> fn is faction N's points (tools/diplomacy.py's numbers), and storage
monkey:finale result {faction, points, tie, week} the winner. A tie for the most points names no winner: staff
decide (docs/SEASONS.md). The winner goes into the news post and the Sunday recap; `result` prints the roster and
the commands that give it the champion's title and helm (rw.champion). The pack doesn't set rw.champion itself:
a pack can only reach players who are online, the roster is the faction numbers as of the last hourly board run,
and the season's champion is the owners' call (docs/SEASONS.md, "The season champion").

When: the border timer (tools/border.py) sends `function monkey:finale/start {x:X,z:Z,cx:CX,cz:CZ}` (the
monument and the border's centre)
from the finale's time (week WEEK's Saturday, 6 PM Pacific) in a season with border acts, once the saved world
shows the switch on (`function monkey:finale/on`, docs/SEASONS.md "Switches"; off in a new world). The pack runs it
once a world, from Season II (`#season rw.day` 2 or more), after the launch and before the lock. In Season I
nothing here runs.

Stdlib only plus tools/saved_world.py and tools/diplomacy.py, Python 3.10 or newer.
"""
import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import saved_world
import season_calendar
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, text
from events import ARENA_TAG, STATE
from repo import Repo

DATAPACK = "monkey-finale"
FN = f"data/{NS}/function/finale"
STORE = f"{NS}:finale"
KEY = "finale"              # STORE's key in the namespace's command storage file
BAR = f"{NS}:finale"
OBJ = "fn"                  # #on, #started, #phase, #t, #f<N> (points), #best, #win, #tie, and scratch
SEASON = "#season rw.day"
LOCKED = "#season_locked"   # in events' ev.state
FACTION = "st.faction"      # tools/diplomacy.py's faction number
MAX_FACTIONS = 99           # diplomacy.MAX_FACTIONS (a test checks they agree)

WEEK = 11                   # the finale's week (docs/SEASONS.md, "The acts of a season")
START = dt.time(18, 0)      # the Saturday event slot, Pacific
WARN_SECONDS = 600          # from the start to the shrink: the 10-minute and 1-minute warnings, then now
SHRINK_SECONDS = 2400       # the shrink
HOLD_SECONDS = 3600         # the last hour: the border holds, presence counts
FINAL_SIZE = 256            # blocks across at the end
MIN_SIZE = 128              # FINAL_SIZE is never set below this (a test checks it)
RADIUS = 24                 # the monument's zone: this many blocks from its centre either way
EDGE_MARGIN = 16            # players this close to the edge (or past it) are warned
EDGE_EVERY = 5              # seconds between edge checks
TICKS = 20                  # `worldborder set SIZE TIME` takes ticks since 26.3
# Where: the monument is MONUMENT_OFFSET blocks (x, z) from the Overworld border's centre, which the rules pack put
# on spawn (docs/RULES.md, rule 25). Never at spawn: spawn is sacred and a no-PvP zone (rules 22 and 26), the server
# claim over its 7 x 7 chunks, so SPAWN_ZONE blocks either way of the centre; the hold zone (RADIUS) and the event
# area (EVENT_RADIUS) stay clear of it (a test checks). Staff build the monument there before the finale.
MONUMENT_OFFSET = (192, 0)
SPAWN_ZONE = 64             # 7 x 7 chunks around spawn reach at most 63 blocks from it
EVENT_RADIUS = 64           # the hold's event area (rule 41): this many blocks from the monument either way
STEER = 1                   # blocks a second the border's centre moves toward the monument, each way

SHRINK_AT = WARN_SECONDS
HOLD_AT = SHRINK_AT + SHRINK_SECONDS
CLOSE_AT = HOLD_AT + HOLD_SECONDS

# What `function monkey:finale/start` returns (the border timer's log reads them through rcon.coded).
CODES = {
    1: "the finale has started: the border closes in 10 minutes",
    10: "the finale is off (function monkey:finale/on)",
    11: "not Season II or later: no finale",
    12: "the season hasn't launched",
    13: "the season is locked",
    14: "the finale has run in this world already",
    15: "the monument is too far from the border's centre for the shrink to reach it",
}


def finale_at(season: int) -> dt.datetime | None:
    """When a season's finale starts: its week WEEK Saturday at 6 PM Pacific. None for a season with no calendar."""
    calendar = season_calendar.SEASONS.get(season)
    if calendar is None:
        return None
    return dt.datetime.combine(calendar.saturday(WEEK), START, season_calendar.PACIFIC)


def monument(center_x: float, center_z: float) -> tuple[int, int]:
    """The monument for an Overworld border centred here (on spawn): MONUMENT_OFFSET from it."""
    return round(center_x) + MONUMENT_OFFSET[0], round(center_z) + MONUMENT_OFFSET[1]


def start_command(center_x: float, center_z: float) -> str:
    """The border timer's start: the monument and the border's centre, which moves to it during the shrink."""
    x, z = monument(center_x, center_z)
    return f"function {NS}:finale/start {{x:{x},z:{z},cx:{round(center_x)},cz:{round(center_z)}}}"


def stages(start: dt.datetime) -> list[tuple[dt.datetime, str]]:
    def at(seconds: int) -> dt.datetime:
        return start + dt.timedelta(seconds=seconds)
    return [(at(0), "warning: the border closes in 10 minutes"),
            (at(SHRINK_AT - 60), "warning: 1 minute"),
            (at(SHRINK_AT), f"the shrink starts: down to {FINAL_SIZE} across over {SHRINK_SECONDS // 60} minutes"),
            (at(HOLD_AT), f"the border holds at {FINAL_SIZE}: the last hour, presence at the monument counts"),
            (at(CLOSE_AT - 600), "10 minutes to the close"),
            (at(CLOSE_AT - 60), "1 minute to the close"),
            (at(CLOSE_AT), "the close: the faction with the most points holds the monument")]


# ---------------------------------------------------------------- the saved world


@dataclass(frozen=True)
class Result:
    faction: int        # the winner's number, 0 when nobody stood there
    points: int         # its member-seconds at the monument in the last hour
    tie: bool           # the most points were shared: no winner named
    week: int | None    # the challenge week it closed in
    points_by: dict[int, int]   # every faction's points, from the scores


def result(world: Path, scores: dict[str, dict[str, int]] | None = None) -> Result | None:
    """The finale's result in the saved world, None before its close."""
    storage = saved_world.command_storage(world, NS) or {}
    rec = storage.get(KEY, {}).get("result")
    if not isinstance(rec, dict):
        return None
    if scores is None:
        board = saved_world.scoreboard(world)
        scores = board.scores if board else {}
    by = {int(k[2:]): v for k, v in scores.get(OBJ, {}).items() if k.startswith("#f") and k[2:].isdigit() and v > 0}

    def num(field: str, default: int = 0) -> int:
        v = rec.get(field)
        return v if isinstance(v, int) else default
    week = num("week", -1)
    return Result(num("faction"), num("points"), num("tie") == 1, week if week >= 0 else None, by)


def roster(world: Path, faction: int, scores: dict[str, dict[str, int]] | None = None) -> list[str]:
    """The players whose faction number is `faction` (st.faction, as of the last board run), by name."""
    if scores is None:
        board = saved_world.scoreboard(world)
        scores = board.scores if board else {}
    return sorted((p for p, n in scores.get(FACTION, {}).items() if n == faction and not p.startswith("#")),
                  key=str.casefold)


def champion_commands(names: list[str], season: int) -> list[str]:
    """What staff run for the winning roster: the helm, and the title team (docs/SEASONS.md, "The season champion")."""
    team = f"champion_s{season}"
    out = [f"team add {team}", f"team modify {team} color gold",
           f'team modify {team} prefix "[S{season} Champion] "']
    for name in names:
        out += [f"team join {team} {name}", f"scoreboard players set {name} rw.champion 1"]
    return out


# ---------------------------------------------------------------- the data pack


OVERWORLD = f"in {saved_world.OVERWORLD}"


def gold(msg: str) -> dict:
    return {"text": msg, "color": "gold"}


def red(msg: str) -> dict:
    return {"text": msg, "color": "red"}


MONUMENT = {"text": "$(x), $(z)", "color": "yellow"}
MONUMENT_SAVED = [{"nbt": "at.x", "storage": STORE, "color": "yellow"}, {"text": ", ", "color": "yellow"},
                  {"nbt": "at.z", "storage": STORE, "color": "yellow"}]


def say_all(*parts) -> str:
    return "tellraw @a " + text("", {"text": "The finale: ", "color": "dark_red", "bold": True}, *parts)


def datapack_files() -> dict[str, str]:
    assert FINAL_SIZE >= MIN_SIZE
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP finale: the border closes on the monument (generated by tools/finale.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:finale/load")

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/finale.py. Scores and storage are kept across restarts; the switch starts off.",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard players add #on {OBJ} 0",
        f"scoreboard players add #started {OBJ} 0",
        f"scoreboard players add #phase {OBJ} 0",
        f"bossbar add {BAR} " + text({"text": "The finale", "color": "gold"}),
        f"bossbar set {BAR} color yellow",
        f"bossbar set {BAR} max {CLOSE_AT}",
        f"schedule function {NS}:finale/second 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:finale/second 20t replace",
        "# 0 before the finale; 1 the warnings, 2 the shrink, 3 the last hour, 4 after the close.",
        f"execute if score #phase {OBJ} matches 1..3 run function {NS}:finale/tick",
        f"execute if score #phase {OBJ} matches 2.. run scoreboard players add #edge {OBJ} 1",
        f"execute if score #edge {OBJ} matches {EDGE_EVERY}.. run function {NS}:finale/edge",
    )
    f[f"{FN}/start.mcfunction"] = lines(
        "# Macro {x, z, cx, cz}: the monument, and the Overworld border's centre now (it moves to the monument",
        "# during the shrink, STEER blocks a second each way, so the border closes on it).",
        "# Sent by the border timer (tools/border.py) at the finale's time, or by staff. Once a world.",
        f"execute unless score #on {OBJ} matches 1 run return 10",
        f"execute unless score {SEASON} matches 2.. run return 11",
        f"execute unless score {LAUNCHED} matches 1 run return 12",
        f"execute if score {LOCKED} {STATE} matches 1 run return 13",
        f"execute if score #started {OBJ} matches 1 run return 14",
        "# The monument within reach of the shrink: |x - cx| and |z - cz| at most SHRINK_SECONDS * STEER.",
        f"$scoreboard players set #a {OBJ} $(x)",
        f"$scoreboard players set #k {OBJ} $(cx)",
        f"scoreboard players operation #a {OBJ} -= #k {OBJ}",
        f"$scoreboard players set #b {OBJ} $(z)",
        f"$scoreboard players set #k {OBJ} $(cz)",
        f"scoreboard players operation #b {OBJ} -= #k {OBJ}",
        f"execute unless score #a {OBJ} matches -{SHRINK_SECONDS * STEER}..{SHRINK_SECONDS * STEER} run return 15",
        f"execute unless score #b {OBJ} matches -{SHRINK_SECONDS * STEER}..{SHRINK_SECONDS * STEER} run return 15",
        f"scoreboard players set #started {OBJ} 1",
        f"scoreboard players set #phase {OBJ} 1",
        f"scoreboard players set #t {OBJ} 0",
        f"scoreboard players set #edge {OBJ} 0",
        f"$data modify storage {STORE} at set value {{x:$(x),z:$(z),x0:$(x),z0:$(z),d:{2 * RADIUS},bx:$(cx),"
        f"bz:$(cz)}}",
        f"$scoreboard players set #mx {OBJ} $(x)",
        f"$scoreboard players set #mz {OBJ} $(z)",
        f"$scoreboard players set #bx {OBJ} $(cx)",
        f"$scoreboard players set #bz {OBJ} $(cz)",
        f"$scoreboard players set #cx {OBJ} $(x)",
        f"$scoreboard players set #cz {OBJ} $(z)",
        f"execute store result storage {STORE} at.x0 int 1 run scoreboard players remove #cx {OBJ} {RADIUS}",
        f"execute store result storage {STORE} at.z0 int 1 run scoreboard players remove #cz {OBJ} {RADIUS}",
        f"bossbar set {BAR} players @a",
        f"bossbar set {BAR} visible true",
        f"execute store result bossbar {BAR} value run scoreboard players get #t {OBJ}",
        "$" + say_all(gold("in 10 minutes the border starts closing on the monument at "), MONUMENT,
                gold(f", down to {FINAL_SIZE} blocks across over {SHRINK_SECONDS // 60} minutes. Then the last "
                     f"hour, a staff event: the faction with the most member-time at the monument (within {RADIUS} "
                     f"blocks) holds it and wins. Within {EVENT_RADIUS} blocks of it anyone can fight anyone "
                     "(rule 41). Spawn stays safe.")),
        "return 1",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        f"scoreboard players add #t {OBJ} 1",
        f"scoreboard players set #left {OBJ} {CLOSE_AT}",
        f"scoreboard players operation #left {OBJ} -= #t {OBJ}",
        f"execute store result bossbar {BAR} value run scoreboard players get #left {OBJ}",
        f"execute if score #t {OBJ} matches {SHRINK_AT - 60} run " + say_all(
            gold("the border starts closing in 1 minute. Head for the monument at "), *MONUMENT_SAVED, gold(".")),
        f"execute if score #t {OBJ} matches {SHRINK_AT} run function {NS}:finale/shrink",
        f"execute if score #t {OBJ} matches {HOLD_AT} run function {NS}:finale/hold",
        f"execute if score #phase {OBJ} matches 2..3 run function {NS}:finale/steer",
        f"execute if score #phase {OBJ} matches 3 run function {NS}:finale/sample with storage {STORE} at",
        f"execute if score #t {OBJ} matches {CLOSE_AT - 600} run " + say_all(
            gold("10 minutes left. Hold the monument.")),
        f"execute if score #t {OBJ} matches {CLOSE_AT - 60} run " + say_all(gold("1 minute left.")),
        f"execute if score #t {OBJ} matches {CLOSE_AT}.. run function {NS}:finale/close",
    )
    f[f"{FN}/shrink.mcfunction"] = lines(
        f"scoreboard players set #phase {OBJ} 2",
        f"bossbar set {BAR} color red",
        "# Never below FINAL_SIZE, and a border already that small is left as it is.",
        f"execute {OVERWORLD} store result score #size {OBJ} run worldborder get",
        f"execute if score #size {OBJ} matches {FINAL_SIZE + 1}.. {OVERWORLD} run "
        f"worldborder set {FINAL_SIZE} {SHRINK_SECONDS * TICKS}",
        say_all({"text": "the border is closing now", "color": "red", "bold": True},
                gold(f", down to {FINAL_SIZE} blocks across around the monument at "), *MONUMENT_SAVED,
                gold(f" over {SHRINK_SECONDS // 60} minutes. Anyone it passes is moved inside.")),
    )
    f[f"{FN}/steer.mcfunction"] = lines(
        "# The border's centre moves to the monument, a block a second each way: with the shrink, an edge moves",
        "# at most about 2.2 blocks a second, under half walking pace.",
        f"execute if score #bx {OBJ} = #mx {OBJ} if score #bz {OBJ} = #mz {OBJ} run return 0",
        f"execute if score #bx {OBJ} < #mx {OBJ} run scoreboard players add #bx {OBJ} {STEER}",
        f"execute if score #bx {OBJ} > #mx {OBJ} run scoreboard players remove #bx {OBJ} {STEER}",
        f"execute if score #bz {OBJ} < #mz {OBJ} run scoreboard players add #bz {OBJ} {STEER}",
        f"execute if score #bz {OBJ} > #mz {OBJ} run scoreboard players remove #bz {OBJ} {STEER}",
        f"execute store result storage {STORE} at.bx int 1 run scoreboard players get #bx {OBJ}",
        f"execute store result storage {STORE} at.bz int 1 run scoreboard players get #bz {OBJ}",
        f"function {NS}:finale/center with storage {STORE} at",
    )
    f[f"{FN}/center.mcfunction"] = lines(f"$execute {OVERWORLD} run worldborder center $(bx) $(bz)")
    f[f"{FN}/hold.mcfunction"] = lines(
        f"scoreboard players set #phase {OBJ} 3",
        say_all(gold(f"the border has closed. The last hour starts now: every second, each faction scores a "
                     f"point for each member within {RADIUS} blocks of the monument at "), *MONUMENT_SAVED,
                gold(f". A staff event: within {EVENT_RADIUS} blocks of the monument anyone can fight anyone "
                     "(rule 41) until the close.")),
    )
    f[f"{FN}/sample.mcfunction"] = lines(
        "# Macro at {x0, z0, d}: each faction member at the monument (survival, not in the arena) scores a point.",
        f"$execute {OVERWORLD} as @a[x=$(x0),y=-64,z=$(z0),dx=$(d),dy=384,dz=$(d),gamemode=survival,"
        f"tag=!{ARENA_TAG},scores={{{FACTION}=1..}}] run function {NS}:finale/count",
    )
    f[f"{FN}/count.mcfunction"] = lines(
        f"execute store result storage {STORE} n.n int 1 run scoreboard players get @s {FACTION}",
        f"function {NS}:finale/add with storage {STORE} n",
    )
    f[f"{FN}/add.mcfunction"] = lines(f"$scoreboard players add #f$(n) {OBJ} 1")

    # ------------------------------------------------ the edge: warn, and move inside anyone it passed
    f[f"{FN}/edge.mcfunction"] = lines(
        f"scoreboard players set #edge {OBJ} 0",
        f"execute {OVERWORLD} store result score #half {OBJ} run worldborder get",
        f"scoreboard players set #k {OBJ} 2",
        f"scoreboard players operation #half {OBJ} /= #k {OBJ}",
        "# The warned box: EDGE_MARGIN inside the edge. The outside box: the border itself, a block over.",
        f"scoreboard players operation #a {OBJ} = #half {OBJ}",
        f"scoreboard players remove #a {OBJ} {EDGE_MARGIN}",
        f"execute if score #a {OBJ} matches ..{RADIUS} run scoreboard players set #a {OBJ} {RADIUS}",
        f"function {NS}:finale/box {{name:\"warn\"}}",
        f"scoreboard players operation #a {OBJ} = #half {OBJ}",
        f"scoreboard players add #a {OBJ} 1",
        f"function {NS}:finale/box {{name:\"out\"}}",
        f"scoreboard players operation #a {OBJ} = #half {OBJ}",
        f"scoreboard players remove #a {OBJ} 8",
        f"execute store result storage {STORE} edge.r int 1 run scoreboard players get #a {OBJ}",
        f"data modify storage {STORE} edge.x set from storage {STORE} at.bx",
        f"data modify storage {STORE} edge.z set from storage {STORE} at.bz",
        f"function {NS}:finale/edge_at with storage {STORE} edge",
    )
    f[f"{FN}/box.mcfunction"] = lines(
        "# Macro {name}: the square #a blocks either way of the border's centre, as a corner and a width, into edge.",
        f"scoreboard players operation #b {OBJ} = #bx {OBJ}",
        f"scoreboard players operation #b {OBJ} -= #a {OBJ}",
        f"$execute store result storage {STORE} edge.$(name)x int 1 run scoreboard players get #b {OBJ}",
        f"scoreboard players operation #b {OBJ} = #bz {OBJ}",
        f"scoreboard players operation #b {OBJ} -= #a {OBJ}",
        f"$execute store result storage {STORE} edge.$(name)z int 1 run scoreboard players get #b {OBJ}",
        f"scoreboard players operation #b {OBJ} = #a {OBJ}",
        f"scoreboard players operation #b {OBJ} += #a {OBJ}",
        f"$execute store result storage {STORE} edge.$(name)d int 1 run scoreboard players get #b {OBJ}",
    )
    f[f"{FN}/edge_at.mcfunction"] = lines(
        "# Macro edge {warnx, warnz, warnd, outx, outz, outd, r}. Overworld players only (distance=0..).",
        f"$execute {OVERWORLD} as @a[distance=0..,gamemode=!spectator,gamemode=!creative] unless entity "
        f"@s[x=$(warnx),y=-64,z=$(warnz),dx=$(warnd),dy=384,dz=$(warnd)] run title @s actionbar " + text(
            "", red("The finale's border is near: head for the monument at "), *MONUMENT_SAVED),
        f"$execute {OVERWORLD} as @a[distance=0..,gamemode=!spectator,gamemode=!creative] unless entity "
        f"@s[x=$(outx),y=-64,z=$(outz),dx=$(outd),dy=384,dz=$(outd)] run function {NS}:finale/inside "
        f"with storage {STORE} edge",
    )
    f[f"{FN}/inside.mcfunction"] = lines(
        "# Macro edge {x, z, r}: as a player outside the border: to a safe spot inside it (around the border's",
        "# centre, not the monument: no free trip to the hold), told why.",
        f"$execute {OVERWORLD} run spreadplayers $(x) $(z) 0 $(r) false @s",
        "tellraw @s " + text(gold("You were outside the finale's border, so you were moved inside it.")),
    )

    # ------------------------------------------------ the close: the most points holds the monument
    f[f"{FN}/close.mcfunction"] = lines(
        f"scoreboard players set #phase {OBJ} 4",
        f"bossbar set {BAR} visible false",
        f"scoreboard players set #best {OBJ} 0",
        f"scoreboard players set #win {OBJ} 0",
        f"scoreboard players set #tie {OBJ} 0",
        f"scoreboard players set #n {OBJ} 1",
        f"function {NS}:finale/pick",
        f"execute if score #tie {OBJ} matches 1 run scoreboard players set #win {OBJ} 0",
        f"data modify storage {STORE} result set value {{faction:0,points:0,tie:0,week:-1}}",
        f"execute store result storage {STORE} result.faction int 1 run scoreboard players get #win {OBJ}",
        f"execute store result storage {STORE} result.points int 1 run scoreboard players get #best {OBJ}",
        f"execute store result storage {STORE} result.tie int 1 run scoreboard players get #tie {OBJ}",
        f"execute store result storage {STORE} result.week int 1 run scoreboard players get #week rc.week",
        f"execute if score #best {OBJ} matches 0 run " + say_all(
            gold("it is over. Nobody held the monument, so nobody wins it.")),
        f"execute if score #tie {OBJ} matches 1 run " + say_all(
            gold("it is over, and it is a tie for the monument. Staff decide the winner.")),
        f"execute if score #win {OBJ} matches 1.. run function {NS}:finale/won with storage {STORE} result",
        "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 0.6",
    )
    f[f"{FN}/pick.mcfunction"] = lines(
        f"# Factions 1 to {MAX_FACTIONS}, one a call: the most points wins; the same most, a tie.",
        f"execute store result storage {STORE} n.n int 1 run scoreboard players get #n {OBJ}",
        f"function {NS}:finale/pick_one with storage {STORE} n",
        f"scoreboard players add #n {OBJ} 1",
        f"execute if score #n {OBJ} matches ..{MAX_FACTIONS} run function {NS}:finale/pick",
    )
    f[f"{FN}/pick_one.mcfunction"] = lines(
        f"$execute unless score #f$(n) {OBJ} matches 1.. run return 0",
        f"$execute if score #f$(n) {OBJ} = #best {OBJ} run return run scoreboard players set #tie {OBJ} 1",
        f"$execute unless score #f$(n) {OBJ} > #best {OBJ} run return 0",
        f"$scoreboard players operation #best {OBJ} = #f$(n) {OBJ}",
        f"$scoreboard players set #win {OBJ} $(n)",
        f"scoreboard players set #tie {OBJ} 0",
    )
    f[f"{FN}/won.mcfunction"] = lines(
        "$tellraw @a " + text("", {"text": "The finale: ", "color": "dark_red", "bold": True},
                              {"nbt": "names.f$(faction)", "storage": f"{NS}:factions", "interpret": True,
                               "color": "yellow", "bold": True},
                              gold(" held the monument and win the finale, with "),
                              {"text": "$(points)", "color": "yellow"}, gold(" points.")),
        "title @a title " + text({"text": "The monument is held", "color": "gold", "bold": True}),
    )

    # ------------------------------------------------ staff
    f[f"{FN}/on.mcfunction"] = lines(
        "# Staff: the switch (docs/SEASONS.md, \"Switches\"). From Season II only.",
        f"execute unless score {SEASON} matches 2.. run return run tellraw @s " + text(red(
            "The finale is for Season II on: this world is Season I (#season rw.day).")),
        f"scoreboard players set #on {OBJ} 1",
        "tellraw @s " + text(gold("The finale is on: the border timer starts it at the finale's time.")),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        "# Staff: the timer won't start it. A finale already running goes on (finale/stop ends one).",
        f"scoreboard players set #on {OBJ} 0",
        "tellraw @s " + text(gold("The finale is off.")),
    )
    f[f"{FN}/stop.mcfunction"] = lines(
        "# Staff: ends a running finale where it is: the border stops where it has got to, no winner is named.",
        f"execute unless score #phase {OBJ} matches 1..3 run return run tellraw @s "
        + text(red("No finale is running.")),
        f"execute {OVERWORLD} store result storage {STORE} stop.size int 1 run worldborder get",
        f"function {NS}:finale/stop_at with storage {STORE} stop",
        f"scoreboard players set #phase {OBJ} 4",
        f"bossbar set {BAR} visible false",
        say_all(gold("staff have stopped it. The border stays where it is.")),
    )
    f[f"{FN}/stop_at.mcfunction"] = lines(f"$execute {OVERWORLD} run worldborder set $(size)")
    f[f"{FN}/status.mcfunction"] = lines(
        "tellraw @s " + text("", gold("Finale: switch "), {"score": {"name": "#on", "objective": OBJ}},
                             gold(", phase "), {"score": {"name": "#phase", "objective": OBJ}},
                             gold(" (0 not yet, 1 warning, 2 shrinking, 3 last hour, 4 over), second "),
                             {"score": {"name": "#t", "objective": OBJ}}, gold(f" of {CLOSE_AT}")),
        "tellraw @s " + text("", gold("Result: "), {"nbt": "result", "storage": STORE, "color": "white"}),
    )
    f[f"{FN}/reset.mcfunction"] = lines(
        "# Staff, test servers only: forget the finale, so it can start again. The border stays as it is.",
        f"execute store result storage {STORE} on int 1 run scoreboard players get #on {OBJ}",
        f"scoreboard players reset * {OBJ}",
        f"execute store result score #on {OBJ} run data get storage {STORE} on",
        f"scoreboard players set #started {OBJ} 0",
        f"scoreboard players set #phase {OBJ} 0",
        f"data remove storage {STORE} result",
        f"bossbar set {BAR} visible false",
    )
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- the command line


def show_result(world: Path) -> int:
    import diplomacy
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    found = result(world, scores)
    if found is None:
        print("The finale hasn't closed in this world.")
        return 1
    names = diplomacy.names(world)
    for n, points in sorted(found.points_by.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {names.get(n, f'faction {n}')}: {points} points")
    if found.tie:
        print(f"A tie on {found.points} points: no winner named. Staff decide (docs/SEASONS.md, \"The finale\").")
        return 0
    if not found.faction:
        print("Nobody held the monument.")
        return 0
    season = scores.get("rw.day", {}).get("#season", 0)
    members = roster(world, found.faction, scores)
    print(f"{names.get(found.faction, f'faction {found.faction}')} held the monument with {found.points} points.")
    print(f"Roster (faction {found.faction} as of the last board run): {', '.join(members) or 'nobody listed'}")
    print("To crown them champion (docs/SEASONS.md, \"Ending a season\", step 4), run each over RCON:")
    for c in champion_commands(members, season):
        print(f"  {c}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The finale: the border closes on the monument.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="the finale's stages, with their times")
    p.add_argument("--season", type=int, default=2)
    p.add_argument("--world", type=Path, help="a saved world: its monument and the start command for it")
    r = sub.add_parser("result", help="who held the monument, the roster and the staff commands")
    r.add_argument("world", type=Path)
    args = ap.parse_args(argv)
    if args.command == "plan":
        start = finale_at(args.season)
        if start is None:
            print(f"no calendar for season {args.season}")
            return 1
        for when, what in stages(start):
            print(f"{season_calendar.words(when)['date']}, {when.astimezone(season_calendar.PACIFIC):%H:%M} "
                  f"Pacific: {what}")
        if args.world:
            b = saved_world.border(args.world)
            x, z = monument(b.center_x, b.center_z)
            print(f"The monument: {x}, {z} (the border's centre {b.center_x:g}, {b.center_z:g}, spawn, plus "
                  f"{MONUMENT_OFFSET}). Build it there; the hold zone is {RADIUS} blocks either way of it.")
            print(f"  {start_command(b.center_x, b.center_z)}")
        return 0
    if not args.world.is_dir():
        print(f"no world folder at {args.world}")
        return 2
    return show_result(args.world)


if __name__ == "__main__":
    sys.exit(main())
