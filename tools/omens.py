"""Omens: short world events nobody announces ahead, on one or two weekday evenings a week.

    python tools/omens.py plan WORLD [--at TIME]       this week's evenings and omens (spoils the surprise)
    python tools/omens.py commands WORLD [--at TIME]   the RCON commands for now (deploy/monkey-omens.sh)
    python tools/datapacks.py                          regenerates the monkey-omens data pack (with the others)

When: PER_WEEK evenings a week, Monday to Friday, never Saturday (event night) or Sunday, from Season I's first
week. Each evening has a start time between 6:00 and 8:50 PM Pacific; deploy/monkey-omens.sh asks every 10
minutes from then until 10 PM, and the pack starts the evening's omen the first time it is asked while
MIN_PLAYERS or more are online in survival, the season has launched, no omen ran that evening, no event is on
(the arena, a raid, Anarchy, the season lock) and no supply drop is on. An evening that never gets 4 players
has no omen: a week has 0 to PER_WEEK.

The seed: the pack draws two random numbers the first time it loads and keeps them in the world's scoreboard
(#key1 and #key2 om); this script reads them from the saved scoreboard and keys an HMAC with them, so the week's
plan (which evenings, what time, which omen) can't be worked out from the repo, only from the server's files.
A world without the key yet (the pack not loaded, or not saved since) gets no omens.

The omens (OMENS, in the order the plan shuffles; the pack tries them in that order and starts the first
that can):
  blood_moon  at the next nightfall: the game on Hard and hostile mobs near players faster and tougher, until
              dawn (or BLOOD_MAX). Each one a player kills drops a little extra (BLOOD_LOOT, BLOOD_CAP each).
              Not when the game is on Peaceful.
  meteor      a supply drop announced 5 minutes ahead, one chest with more in it (tools/drops.py, "Meteor").
              Not while automatic drops are off, and only on dry, natural ground, as a drop.
  truce       Truce Hour: `gamerule pvp false` for TRUCE_MINUTES. Not when PvP is off already.
  hunted      the player online with the longest kill streak (HUNT_MIN kills or more without dying, outside
              the arena, counted since the launch) is hunted for HUNT_MINUTES: a bounty is posted with the
              standings' bounty/post, and whoever kills them tells staff, who check the kill and run
              bounty/claim as for any bounty (+5 standings points, the Bounty Hunter title). Nothing about where
              they are is shown.
Nothing an omen gives helps in a fight or beats progression: no Strength, nothing the rules ban, no diamonds.

The data pack (package/monkey/datapacks/monkey-omens/, generated: edit this file, not it) has the staff
commands too (docs/ADMIN.md, "Omens"). Stdlib only plus tools/saved_world.py and tools/drops.py, and Python 3.10
or newer, so the VPS runs it straight from the checkout.
"""
import argparse
import datetime as dt
import hashlib
import hmac
import itertools
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

import drops
import rcon as server
import saved_world
import season_calendar
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, refuse, say, text
from events import ARENA_TAG, STATE
from repo import Repo
from rules import OBJECTIVE as RULES

DATAPACK = "monkey-omens"
FN = f"data/{NS}/function/omens"
STORE = f"{NS}:omens"
BAR = f"{NS}:omen"
OBJ = "om"

OMENS = ("blood_moon", "meteor", "truce", "hunted")   # an omen's number (its #state) is its place here, from 1
NAMES = {"blood_moon": "Blood Moon", "meteor": "Meteor", "truce": "Truce Hour", "hunted": "Hunted"}
EVENINGS = (0, 1, 2, 3, 4)   # Monday to Friday
PER_WEEK = 2
HOURS = (18, 22)             # asked from the evening's start until 10 PM Pacific
LATEST_START = 20 * 60 + 50  # an evening's start is a 10-minute slot from 6:00 to 8:50 PM
SLOT_MINUTES = 10
MIN_PLAYERS = 4

BLOOD_WAIT = 21 * 60         # seconds a Blood Moon waits for nightfall: a Minecraft day is 20 minutes
BLOOD_MAX = 15 * 60          # and lasts at most, though a night is shorter (about 8 minutes)
RISE = (13000, 14000)        # it rises only as a night starts (`time query minecraft:day`), never just before dawn
BLOOD_BUFF = 3               # seconds of Speed and Resistance, given again each second while the moon is up
BLOOD_REACH = 48             # blocks around a survival player in the Overworld where mobs are roused
BLOOD_CAP = 20               # bonus drops per player in one Blood Moon
NIGHT = (13000, 22999)       # `time query minecraft:day` from dusk to dawn
TRUCE_MINUTES = 60
HUNT_MIN = 3                 # kills without dying to be hunted
HUNT_MINUTES = 30
HUNT_CHOICES = 5             # the longest streaks sent; the pack takes the first one online
# A Meteor holds the drop for up to its countdown and despawn time, and the drops' timer asks every 10 minutes:
# on a drop night, a Meteor this close to 10 PM only comes once the night's own drop has happened.
METEOR_LATE = dt.timedelta(seconds=drops.METEOR_COUNTDOWN + drops.DESPAWN, minutes=drops.SLOT_MINUTES)
PLAYER = re.compile(r"[A-Za-z0-9_]{1,16}")

# Mobs a Blood Moon rouses: the ones that come out at night in the Overworld. Not the Warden, ravagers or
# guardians or endermen: faster and tougher, they would be more than a night's trouble.
BLOOD_MOBS = ["zombie", "husk", "drowned", "zombie_villager", "skeleton", "stray", "bogged", "creeper", "spider",
              "cave_spider", "witch", "slime", "phantom", "pillager", "vindicator"]
BLOOD_MOBS_OPTIONAL = ["parched", "camel_husk"]   # newer: the tag still loads on a Minecraft without them
# One roll per roused mob a player kills, on top of what it drops anyway: (item, weight, min, max).
BLOOD_LOOT = [
    ("bone", 3, 1, 3),
    ("string", 3, 1, 3),
    ("gunpowder", 2, 1, 2),
    ("arrow", 3, 2, 6),
    ("iron_nugget", 3, 2, 5),
    ("gold_nugget", 2, 2, 5),
    ("experience_bottle", 1, 1, 2),
]
BLOOD_LOOT_TABLE = f"{NS}:omens/blood_moon"

# What `function monkey:omens/try` returns, for the timer's log (meaning()).
TRY_CODES = {
    1: "started",
    20: "automatic omens are off (function monkey:omens/on)",
    21: "an omen is already on",
    22: "tonight's omen already happened",
    23: "an event is on (the arena, a raid, Anarchy or the season lock)",
    24: "a supply drop is on",
    25: "fewer survival players online than the minimum",
    26: "the season hasn't launched",
    27: "none of tonight's omens could start (Peaceful, PvP off, drops off or no dry ground, no one hunted)",
}

HELP = [
    ("start/blood_moon", "at the next nightfall (not on Peaceful)"),
    ("start/truce", f"no PvP for {TRUCE_MINUTES} minutes"),
    ('hunt {name:"Alex"}', f"hunt Alex for {HUNT_MINUTES} minutes (online, in survival)"),
    ("stop", "ends the omen that is on"),
    ("status", "what's on, and the settings"),
    ("min {players:4}", "survival players needed for an evening's omen"),
    ("off", "no automatic omens until on"),
    ("on", "automatic omens again"),
]


# ---------------------------------------------------------------- when


class Evening(NamedTuple):
    day: dt.date
    start: dt.datetime   # Pacific
    order: tuple[str, ...]

    @property
    def night(self) -> int:
        return int(self.day.strftime("%Y%m%d"))


def key(scores: dict[str, dict[str, int]]) -> str | None:
    """The world's secret (the pack's two random numbers), or None when they aren't saved yet."""
    held = scores.get(OBJ, {})
    if not held.get("#key1") or not held.get("#key2"):
        return None
    return f"{held['#key1']}.{held['#key2']}"


def plan(secret: str, week: int) -> list[Evening]:
    """The evenings of a season week (1 and on) that get an omen, earliest first. The same secret and week always
    give the same plan; it is worked out from HMAC bytes, not random.Random, so a new Python can't change it."""
    if week < 1:
        return []
    d = hmac.new(secret.encode(), f"omens week {week}".encode(), hashlib.sha256).digest()
    days = list(itertools.combinations(EVENINGS, PER_WEEK))
    orders = list(itertools.permutations(OMENS))
    picked = days[int.from_bytes(d[0:2], "big") % len(days)]
    order = orders[int.from_bytes(d[2:4], "big") % len(orders)]
    slots = (LATEST_START - HOURS[0] * 60) // SLOT_MINUTES + 1
    monday = season_calendar.week_start(week)
    out = []
    for i, weekday in enumerate(picked):
        day = monday + dt.timedelta(days=weekday)
        minutes = HOURS[0] * 60 + d[4 + i] % slots * SLOT_MINUTES
        start = dt.datetime.combine(day, dt.time(minutes // 60, minutes % 60), season_calendar.PACIFIC)
        out.append(Evening(day, start, order[i % len(order):] + order[:i % len(order)]))
    return out


def evening_of(secret: str, when: dt.datetime) -> Evening | None:
    """The evening `when` is in, from its start until 10 PM Pacific, or None."""
    local = when.astimezone(season_calendar.PACIFIC)
    if local.hour >= HOURS[1]:
        return None
    for evening in plan(secret, season_calendar.week_at(when)):
        if evening.day == local.date() and local >= evening.start:
            return evening
    return None


# ---------------------------------------------------------------- what the pack is sent


def hunt_choices(scores: dict[str, dict[str, int]]) -> list[str]:
    """The longest kill streaks saved, HUNT_MIN and over, longest first (names as typed in game)."""
    streaks = [(v, name) for name, v in scores.get("om.streak", {}).items()
               if v >= HUNT_MIN and PLAYER.fullmatch(name)]
    return [name for _, name in sorted(streaks, key=lambda s: (-s[0], s[1].lower()))[:HUNT_CHOICES]]


def commands(world: Path, when: dt.datetime) -> list[str]:
    """What deploy/monkey-omens.sh sends: nothing outside an evening's omen hours, else the evening's order, what
    the omens in it need (the meteor's spots, the hunt's names), and the try. An omen with nothing to work with
    (no spots, no streak) is left out of the order. `late` tells the pack a Meteor now would keep the night's
    supply drop from coming before 10 PM (METEOR_LATE)."""
    local = when.astimezone(season_calendar.PACIFIC)
    if (local.weekday() not in EVENINGS or not HOURS[0] <= local.hour < HOURS[1]
            or season_calendar.week_at(when) < 1):
        return []   # most of the 144 runs a day: not an evening's hours, so the saved world isn't read
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    secret = key(scores)
    evening = evening_of(secret, when) if secret else None
    if evening is None:
        return []
    out = []
    order = list(evening.order)
    if "meteor" in order:
        found = drops.spots(world, "meteor " + drops.slot_of(when))
        if found:
            out.append(f"data modify storage {STORE} spots set value [" +
                       ",".join(f"{{x:{x},z:{z}}}" for x, z in found) + "]")
        else:
            order.remove("meteor")
    if "hunted" in order:
        names = hunt_choices(scores)
        if names:
            out.append(f"data modify storage {STORE} hunt set value [" +
                       ",".join(f'{{name:"{n}"}}' for n in names) + "]")
        else:
            order.remove("hunted")
    out.insert(0, f"data modify storage {STORE} order set value [" + ",".join(f'"{o}"' for o in order) + "]")
    late = int(drops.night_of(when) is not None and local + METEOR_LATE >= local.replace(hour=HOURS[1], minute=0,
                                                                                            second=0, microsecond=0))
    out.append(f"function {NS}:omens/try {{night:{evening.night},late:{late}}}")
    return out


# ---------------------------------------------------------------- reading what happened (for the weekly recap)


def ran(scores: dict[str, dict[str, int]]) -> dict[dt.date, str]:
    """The evenings an omen started on its own, and which (from the saved scoreboard's #on.YYYYMMDD om)."""
    out = {}
    for holder, n in scores.get(OBJ, {}).items():
        m = re.fullmatch(r"#on\.(\d{4})(\d{2})(\d{2})", holder)
        if m and 1 <= n <= len(OMENS):
            out[dt.date(int(m[1]), int(m[2]), int(m[3]))] = OMENS[n - 1]
    return dict(sorted(out.items()))


def in_week(scores: dict[str, dict[str, int]], week: int) -> dict[dt.date, str]:
    """ran() for one season week, Monday to Sunday."""
    start = season_calendar.week_start(week)
    return {day: omen for day, omen in ran(scores).items() if start <= day < start + dt.timedelta(days=7)}


# ---------------------------------------------------------------- the data pack


def score(holder: str, color: str = "white", objective: str = OBJ) -> dict:
    return {"score": {"name": holder, "objective": objective}, "color": color}


def head(omen: str, color: str) -> dict:
    return {"text": NAMES[omen] + ": ", "color": color, "bold": True}


TARGET = {"nbt": "target.name", "storage": STORE, "color": "white"}
EVENTS_ON = drops.EVENTS_ON
STATES = {omen: i for i, omen in enumerate(OMENS, 1)}
TO_ALL = "execute as @a at @s run "


def bar_tick(label: list, color: str) -> list[str]:
    """Each second while an omen with a boss bar is on: the bar's value and its minutes left."""
    return [f"scoreboard players operation #mins {OBJ} = #timer {OBJ}",
            f"scoreboard players add #mins {OBJ} 59",
            f"scoreboard players operation #mins {OBJ} /= #60 {OBJ}",
            f"execute store result bossbar {BAR} value run scoreboard players get #timer {OBJ}",
            f"bossbar set {BAR} players @a",
            f"bossbar set {BAR} name " + text({"text": "", "color": color}, *label, score("#mins"),
                                              {"text": " min", "color": color})]


def bar_add(omen: str, color: str, seconds: int) -> list[str]:
    return [f"bossbar remove {BAR}",
            f"bossbar add {BAR} " + text({"text": NAMES[omen], "color": color}),
            f"bossbar set {BAR} color {color}",
            f"bossbar set {BAR} max {seconds}",
            f"bossbar set {BAR} value {seconds}",
            f"bossbar set {BAR} players @a",
            f"bossbar set {BAR} visible true"]


def loot_table() -> dict:
    return {"type": "minecraft:chest", "pools": [{"rolls": 1, "entries": [
        {"type": "minecraft:item", "name": f"minecraft:{item}", "weight": weight} | (
            {"modifier": {"type": "minecraft:set_count", "count": {"type": "minecraft:uniform", "min": a, "max": b}}}
            if b > 1 else {})
        for item, weight, a, b in BLOOD_LOOT]}]}


def kill_advancement(name: str, entity: dict) -> str:
    """A hidden advancement for a player killing `entity` (26.x shapes: one condition, named by "type"), whose
    reward takes it back so it fires again."""
    return json.dumps({"criteria": {"kill": {"trigger": "minecraft:player_killed_entity",
                                             "conditions": {"entity": entity}}},
                       "requirements": [["kill"]],
                       "rewards": {"function": f"{NS}:omens/{name}"}}, indent=2)


# The Blood Moon on now (#moon om), as an advancement's number: a kill pays only for a mob roused at this one.
MOON = {"type": "minecraft:score", "target": {"type": "minecraft:fixed", "name": "#moon"}, "score": OBJ}


def has_score(objective: str) -> dict:
    return {"type": "minecraft:entity_scores", "entity": "this", "scores": {objective: {"min": 1}}}


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP omens (generated by tools/omens.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:omens/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:omens/tick")
    f[f"data/{NS}/loot_table/omens/blood_moon.json"] = json.dumps(loot_table(), indent=2)
    f[f"data/{NS}/tags/entity_type/omens/blood_moon.json"] = json.dumps({"values": [
        *(f"minecraft:{m}" for m in BLOOD_MOBS),
        *({"id": f"minecraft:{m}", "required": False} for m in BLOOD_MOBS_OPTIONAL)]}, indent=2)
    f[f"data/{NS}/advancement/omens/blood_kill.json"] = kill_advancement("blood_moon/kill", {
        "type": "minecraft:entity_scores", "entity": "this", "scores": {"om.blood": {"min": MOON, "max": MOON}}})
    f[f"data/{NS}/advancement/omens/hunted_kill.json"] = kill_advancement("hunted/kill", {
        "type": "minecraft:all_of", "terms": [
            {"type": "minecraft:entity_properties", "entity": "this",
             "predicate": {"minecraft:entity_type": "minecraft:player"}},
            has_score("om.hunt")]})

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/omens.py. Scores and storage are kept across restarts, and an omen that was on",
        "# carries on where it was.",
        f"scoreboard objectives add {OBJ} dummy",
        "scoreboard objectives add om.pk playerKillCount",
        "scoreboard objectives add om.deaths deathCount",
        "scoreboard objectives add om.streak dummy",
        "scoreboard objectives add om.blood dummy",
        "scoreboard objectives add om.loot dummy",
        "scoreboard objectives add om.hunt dummy",
        f"scoreboard players set #60 {OBJ} 60",
        f"execute unless score #min {OBJ} matches 1.. run scoreboard players set #min {OBJ} {MIN_PLAYERS}",
        f"execute unless score #auto {OBJ} matches 0.. run scoreboard players set #auto {OBJ} 1",
        f"execute unless score #state {OBJ} matches 0.. run scoreboard players set #state {OBJ} 0",
        f"execute unless score #moon {OBJ} matches 0.. run scoreboard players set #moon {OBJ} 0",
        "# The secret tools/omens.py plans the weeks with: drawn once, never shown, never changed.",
        f"execute unless score #key1 {OBJ} matches 1.. store result score #key1 {OBJ} run random value 1..1000000000",
        f"execute unless score #key2 {OBJ} matches 1.. store result score #key2 {OBJ} run random value 1..1000000000",
        f"schedule function {NS}:omens/second 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        "# Kill streaks, for Hunted: player kills outside the event arena add up, from the launch on; dying",
        "# outside the arena starts again from 0.",
        f"execute if score {LAUNCHED} matches 1 as @a[scores={{om.pk=1..}},tag=!{ARENA_TAG}] run "
        "scoreboard players operation @s om.streak += @s om.pk",
        "scoreboard players set @a[scores={om.pk=1..}] om.pk 0",
        f"execute if score #state {OBJ} matches {STATES['hunted']} as @a[scores={{om.hunt=1..,om.deaths=1..}}] run "
        f"function {NS}:omens/hunted/died",
        f"scoreboard players set @a[scores={{om.deaths=1..}},tag=!{ARENA_TAG}] om.streak 0",
        "scoreboard players set @a[scores={om.deaths=1..}] om.deaths 0",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:omens/second 20t replace",
        "# Test play before the launch builds no streak.",
        f"execute unless score {LAUNCHED} matches 1 run scoreboard players reset * om.streak",
        f"execute if score #state {OBJ} matches 0 run return 0",
        *(f"execute if score {cond} run return run function {NS}:omens/interrupted" for cond in EVENTS_ON),
        f"execute if score #state {OBJ} matches {STATES['blood_moon']} run function {NS}:omens/blood_moon/second",
        "# A Meteor: announced once the drop counts down (#phase 1); no dry ground at any spot, and it never came.",
        f"execute if score #state {OBJ} matches {STATES['meteor']} if score #state {drops.OBJ} matches 2.. run "
        f"scoreboard players set #phase {OBJ} 1",
        f"execute if score #state {OBJ} matches {STATES['meteor']} if score #phase {OBJ} matches 0 unless score "
        f"#state {drops.OBJ} matches 1.. run function {NS}:omens/meteor/failed",
        f"execute if score #state {OBJ} matches {STATES['meteor']} if score #phase {OBJ} matches 1 unless score "
        f"#state {drops.OBJ} matches 1.. run function {NS}:omens/end",
        f"execute if score #state {OBJ} matches {STATES['truce']} run function {NS}:omens/truce/second",
        f"execute if score #state {OBJ} matches {STATES['hunted']} run function {NS}:omens/hunted/second",
    )

    # ---- starting
    f[f"{FN}/try.mcfunction"] = lines(
        "# The evening's omen: deploy/monkey-omens.sh calls this every 10 minutes from the evening's start until",
        f"# 10 PM, after putting the order (and the meteor's spots, the hunt's names) in storage {STORE}. Returns",
        "# why it didn't start (tools/omens.py TRY_CODES).",
        f"execute unless score #auto {OBJ} matches 1 run return 20",
        f"execute unless score {LAUNCHED} matches 1 run return 26",
        f"execute if score #state {OBJ} matches 1.. run return 21",
        f"$execute if score #night {OBJ} matches $(night) run return 22",
        *(f"execute if score {cond} run return 23" for cond in EVENTS_ON),
        f"execute if score #state {drops.OBJ} matches 1.. run return 24",
        f"execute store result score #online {OBJ} if entity @a[gamemode=survival]",
        f"execute if score #online {OBJ} < #min {OBJ} run return 25",
        f"$data modify storage {STORE} tonight set value {{night:$(night)}}",
        f"$scoreboard players set #tonight {OBJ} $(night)",
        f"$scoreboard players set #late {OBJ} $(late)",
        f"execute store result score #r {OBJ} run function {NS}:omens/pick",
        f"execute unless score #r {OBJ} matches 1 run return 27",
        f"scoreboard players operation #prev {OBJ} = #night {OBJ}",
        f"scoreboard players operation #night {OBJ} = #tonight {OBJ}",
        f"function {NS}:omens/record with storage {STORE} tonight",
        "return 1",
    )
    f[f"{FN}/record.mcfunction"] = lines(
        "# Macro {night:20261124}: the evening's omen, for the weekly recap (tools/omens.py ran()).",
        f"$scoreboard players operation #on.$(night) {OBJ} = #state {OBJ}",
    )
    f[f"{FN}/unrecord.mcfunction"] = lines(f"$scoreboard players reset #on.$(night) {OBJ}")
    f[f"{FN}/pick.mcfunction"] = lines(
        "# Tries the omens in the order sent, first to last; returns 1 for the first that starts.",
        f"execute unless data storage {STORE} order[0] run return 0",
        f"data modify storage {STORE} next set value {{}}",
        f"data modify storage {STORE} next.id set from storage {STORE} order[0]",
        f"data remove storage {STORE} order[0]",
        f"execute store result score #r {OBJ} run function {NS}:omens/begin with storage {STORE} next",
        f"execute if score #r {OBJ} matches 1 run return 1",
        f"return run function {NS}:omens/pick",
    )
    f[f"{FN}/begin.mcfunction"] = lines(f"$return run function {NS}:omens/$(id)/begin")

    # ---- Blood Moon
    bm = f"{FN}/blood_moon"
    night = f"{NIGHT[0]}..{NIGHT[1]}"
    rise = f"{RISE[0]}..{RISE[1]}"
    blood = f"@e[type=#{NS}:omens/blood_moon"
    f[f"{bm}/begin.mcfunction"] = lines(
        "# Returns 1 when it starts: it waits for nightfall, then rises. Not on Peaceful (no mobs).",
        f"execute store result score #diff {OBJ} run difficulty",
        f"execute if score #diff {OBJ} matches 0 run return 0",
        f"scoreboard players set #state {OBJ} {STATES['blood_moon']}",
        f"scoreboard players set #phase {OBJ} 0",
        f"scoreboard players set #timer {OBJ} {BLOOD_WAIT}",
        "tellraw @a " + text({"text": "The moon is coming up red tonight.", "color": "dark_red", "italic": True}),
        "return 1",
    )
    f[f"{bm}/second.mcfunction"] = lines(
        f"scoreboard players remove #timer {OBJ} 1",
        f"execute store result score #now {OBJ} run time query minecraft:day",
        "# It rises at nightfall only, so it never comes up just before dawn.",
        f"execute if score #phase {OBJ} matches 0 if score #now {OBJ} matches {rise} run return run "
        f"function {NS}:omens/blood_moon/rise",
        f"execute if score #phase {OBJ} matches 0 if score #timer {OBJ} matches ..0 run return run "
        f"function {NS}:omens/blood_moon/fade",
        f"execute if score #phase {OBJ} matches 0 run return 0",
        f"execute unless score #now {OBJ} matches {night} run return run function {NS}:omens/blood_moon/dawn",
        f"execute if score #timer {OBJ} matches ..0 run return run function {NS}:omens/blood_moon/dawn",
        *bar_tick([{"text": "Blood Moon: ", "bold": True}, {"text": "until dawn, at most "}], "red"),
        f"execute as @a[gamemode=survival,tag=!{ARENA_TAG}] at @s if dimension {saved_world.OVERWORLD} as "
        f"{blood},distance=..{BLOOD_REACH}] run function {NS}:omens/blood_moon/rouse",
    )
    f[f"{bm}/rise.mcfunction"] = lines(
        "# Nightfall: Hard until dawn (the difficulty it was on comes back then). Staff set Peaceful since it",
        "# was announced: no mobs, so it fades.",
        f"execute store result score #diff {OBJ} run difficulty",
        f"execute if score #diff {OBJ} matches 0 run return run function {NS}:omens/blood_moon/fade",
        "# This moon's number: a mob roused tonight carries it (om.blood), so one roused at an earlier moon and",
        "# never calmed (its chunk was unloaded) pays nothing.",
        f"scoreboard players add #moon {OBJ} 1",
        "difficulty hard",
        f"scoreboard players set #phase {OBJ} 1",
        f"scoreboard players set #timer {OBJ} {BLOOD_MAX}",
        "scoreboard players reset * om.loot",
        *bar_add("blood_moon", "red", BLOOD_MAX),
        'title @a times 10 60 20',
        "title @a subtitle " + text({"text": "until dawn", "color": "red"}),
        "title @a title " + text({"text": NAMES["blood_moon"], "color": "dark_red", "bold": True}),
        "tellraw @a " + text(head("blood_moon", "dark_red"),
                             {"text": "until dawn the game is on Hard, and mobs near players are faster and tougher. "
                                      f"Each one you kill drops a little extra (up to {BLOOD_CAP} each). Sleeping "
                                      "through the night ends it.", "color": "red"}),
        TO_ALL + "playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.4 0.6",
    )
    f[f"{bm}/rouse.mcfunction"] = lines(
        f"# Each second, as a hostile mob near a player: faster and tougher for {BLOOD_BUFF} seconds (so it wears",
        "# off soon after dawn, loaded or not), and marked with this moon's number for the bonus drop.",
        f"scoreboard players operation @s om.blood = #moon {OBJ}",
        f"effect give @s minecraft:speed {BLOOD_BUFF} 0 true",
        f"effect give @s minecraft:resistance {BLOOD_BUFF} 0 true",
    )
    f[f"{bm}/kill.mcfunction"] = lines(
        "# A player killed a roused mob (advancement monkey:omens/blood_kill): the bonus drop, at their feet.",
        "advancement revoke @s only monkey:omens/blood_kill",
        f"execute unless score #state {OBJ} matches {STATES['blood_moon']} run return 0",
        f"execute unless score #phase {OBJ} matches 1 run return 0",
        f"execute if score @s om.loot matches {BLOOD_CAP}.. run return 0",
        "scoreboard players add @s om.loot 1",
        f"loot spawn ~ ~ ~ loot {BLOOD_LOOT_TABLE}",
    )
    f[f"{bm}/fade.mcfunction"] = lines(
        "# Night never came (the daylight cycle is off, or time was changed): it fades without rising.",
        "tellraw @a " + text({"text": "The red moon faded before nightfall.", "color": "gray", "italic": True}),
        f"function {NS}:omens/end",
    )
    f[f"{bm}/dawn.mcfunction"] = lines(
        "tellraw @a " + text(head("blood_moon", "dark_red"),
                             {"text": "it's over. The mobs calm down and the difficulty is back.", "color": "gray"}),
        f"function {NS}:omens/end",
    )
    f[f"{bm}/calm.mcfunction"] = lines(
        "# The end of a Blood Moon: the mobs' effects wear off in seconds, and the difficulty comes back, unless",
        "# staff changed it meanwhile or the season was locked (it sets Peaceful).",
        f"scoreboard players reset {blood},scores={{om.blood=1..}}] om.blood",
        f"execute unless score #phase {OBJ} matches 1 run return 0",
        f"execute store result score #now {OBJ} run difficulty",
        f"execute unless score #now {OBJ} matches 3 run return 0",
        f"execute if score #season_locked {STATE} matches 1 run return 0",
        f"execute if score #diff {OBJ} matches 0 run difficulty peaceful",
        f"execute if score #diff {OBJ} matches 1 run difficulty easy",
        f"execute if score #diff {OBJ} matches 2 run difficulty normal",
    )

    # ---- Meteor (tools/drops.py does the drop; the omen only starts it)
    f[f"{FN}/meteor/begin.mcfunction"] = lines(
        "# Returns 1 when the Meteor starts: the drop checks the ground at the spots sent and counts down. Close",
        "# to 10 PM on a drop night (#late) it waits for the night's own supply drop: it would keep that one away.",
        f"execute unless data storage {STORE} spots[0] run return 0",
        f"execute if score #late {OBJ} matches 1 unless score #night {drops.OBJ} = #tonight {OBJ} run return 0",
        f"data modify storage {drops.STORE} spots set from storage {STORE} spots",
        f"data remove storage {STORE} spots",
        f"execute store result score #r {OBJ} run function {NS}:drops/meteor",
        f"execute unless score #r {OBJ} matches 1 run return 0",
        f"scoreboard players set #state {OBJ} {STATES['meteor']}",
        "return 1",
    )

    f[f"{FN}/meteor/failed.mcfunction"] = lines(
        "# The drop found no dry ground at any spot, so the Meteor never came: tonight's omen isn't used up, and",
        "# the next omen in the order is tried now.",
        f"scoreboard players set #state {OBJ} 0",
        f"scoreboard players set #phase {OBJ} 0",
        f"execute store result score #r {OBJ} run function {NS}:omens/pick",
        f"execute if score #r {OBJ} matches 1 run return run function {NS}:omens/record with storage {STORE} tonight",
        f"function {NS}:omens/unrecord with storage {STORE} tonight",
        f"scoreboard players operation #night {OBJ} = #prev {OBJ}",
    )

    # ---- Truce Hour
    tr = f"{FN}/truce"
    f[f"{tr}/begin.mcfunction"] = lines(
        "# Returns 1 when it starts. Not when PvP is off already (the launch hour, the season lock, staff).",
        f"execute store result score #pvp {OBJ} run gamerule pvp",
        f"execute unless score #pvp {OBJ} matches 1 run return 0",
        f"execute if score #launching {RULES} matches 1 run return 0",
        "gamerule pvp false",
        f"scoreboard players set #state {OBJ} {STATES['truce']}",
        f"scoreboard players set #timer {OBJ} {TRUCE_MINUTES * 60}",
        *bar_add("truce", "green", TRUCE_MINUTES * 60),
        "title @a times 10 60 20",
        "title @a title " + text({"text": NAMES["truce"], "color": "green", "bold": True}),
        "tellraw @a " + text(head("truce", "green"),
                             {"text": f"for the next {TRUCE_MINUTES} minutes no player can hurt another, anywhere. "
                                      "Claims and the rules work as always. PvP comes back on at the end.",
                              "color": "yellow"}),
        TO_ALL + "playsound minecraft:block.bell.use master @s ~ ~ ~ 1 0.8",
        "return 1",
    )
    f[f"{tr}/second.mcfunction"] = lines(
        f"scoreboard players remove #timer {OBJ} 1",
        *bar_tick([{"text": "Truce Hour: ", "bold": True}, {"text": "no PvP for "}], "green"),
        f"execute if score #timer {OBJ} matches 300 run tellraw @a " + text(
            head("truce", "green"), {"text": "5 minutes until PvP is back on.", "color": "yellow"}),
        f"execute if score #timer {OBJ} matches ..0 run function {NS}:omens/truce/over",
    )
    f[f"{tr}/over.mcfunction"] = lines(
        "tellraw @a " + text(head("truce", "green"), {"text": "it's over: PvP is back on.", "color": "red"}),
        f"function {NS}:omens/end",
    )
    f[f"{tr}/restore.mcfunction"] = lines(
        "# PvP back on, unless something else turned it off meanwhile (the season lock, the launch hour) or",
        "# staff turned it on again already.",
        f"execute if score #season_locked {STATE} matches 1 run return 0",
        f"execute if score #launching {RULES} matches 1 run return 0",
        "gamerule pvp true",
    )

    # ---- Hunted
    hu = f"{FN}/hunted"
    hunted_bar = [f"scoreboard players set #state {OBJ} {STATES['hunted']}",
                  f"scoreboard players set #phase {OBJ} 0",   # 1 once they are killed (hunted/over)
                  f"scoreboard players set #timer {OBJ} {HUNT_MINUTES * 60}",
                  *bar_add("hunted", "red", HUNT_MINUTES * 60)]
    f[f"{hu}/begin.mcfunction"] = lines(
        "# Returns 1 when it starts: the first of the names sent who is online in survival, outside the arena,",
        f"# with a streak of {HUNT_MIN} or more now.",
        f"execute unless data storage {STORE} hunt[0] run return 0",
        f"data modify storage {STORE} target set from storage {STORE} hunt[0]",
        f"data remove storage {STORE} hunt[0]",
        f"execute store result score #r {OBJ} run function {NS}:omens/hunted/mark with storage {STORE} target",
        f"execute if score #r {OBJ} matches 1 run return 1",
        f"return run function {NS}:omens/hunted/begin",
    )
    f[f"{hu}/mark.mcfunction"] = lines(
        "# Macro {name:\"Alex\"}: Alex is hunted, if online in survival outside the arena with the streak.",
        f"$execute unless entity @a[name=$(name),gamemode=survival,tag=!{ARENA_TAG}] run return 0",
        f"$execute unless score $(name) om.streak matches {HUNT_MIN}.. run return 0",
        f"$function {NS}:omens/hunted/on {{name:\"$(name)\"}}",
        "return 1",
    )
    f[f"{hu}/on.mcfunction"] = lines(
        "# Macro {name:\"Alex\"}: the hunt on Alex starts (the name is in storage target too).",
        "scoreboard players reset * om.hunt",
        "$scoreboard players set $(name) om.hunt 1",
        *hunted_bar,
        "title @a times 10 60 20",
        "title @a title " + text({"text": NAMES["hunted"], "color": "red", "bold": True}),
        "$title @a subtitle " + text({"text": "$(name)", "color": "white"}),
        "$tellraw @a " + text(head("hunted", "red"), {"text": "$(name)", "color": "white"},
                              {"text": " is hunted (kills in a row without dying: ", "color": "yellow"},
                              {"score": {"name": "$(name)", "objective": "om.streak"}, "color": "aqua"},
                              {"text": f"). For the next {HUNT_MINUTES} minutes there is a bounty on them; it ends "
                                       "with the hunt. $(name): stay alive.", "color": "yellow"}),
        f"$function {NS}:standings/bounty/post {{target:\"$(name)\"}}",
        TO_ALL + "playsound minecraft:entity.wolf.howl master @s ~ ~ ~ 0.6 0.9",
    )
    f[f"{hu}/second.mcfunction"] = lines(
        f"scoreboard players remove #timer {OBJ} 1",
        *bar_tick([{"text": "Hunted: ", "bold": True}, TARGET, {"text": " for "}], "red"),
        f"execute unless entity @a[scores={{om.hunt=1..}}] run return run function {NS}:omens/hunted/left",
        f"execute if score #timer {OBJ} matches ..0 run function {NS}:omens/hunted/survived",
    )
    f[f"{hu}/over.mcfunction"] = lines(
        "# From end: the hunt's bounty is over (a kill during it sets #phase 1 first, and stays claimable).",
        f"execute if score #phase {OBJ} matches 1 run return 0",
        "tellraw @a " + text(head("hunted", "red"), {"text": "the bounty on ", "color": "gray"}, TARGET,
                             {"text": " is withdrawn: a kill from now on doesn't claim it.", "color": "gray"}),
    )
    f[f"{hu}/kill.mcfunction"] = lines(
        "# A player killed the hunted player (advancement monkey:omens/hunted_kill). Staff check the kill as for",
        "# any bounty, then claim it for them with standings' bounty/claim.",
        "advancement revoke @s only monkey:omens/hunted_kill",
        f"execute unless score #state {OBJ} matches {STATES['hunted']} run return 0",
        f"execute if entity @s[tag={ARENA_TAG}] run return 0",
        "tellraw @a " + text(head("hunted", "red"), {"selector": "@s", "color": "white"},
                             {"text": " killed ", "color": "yellow"}, TARGET,
                             {"text": ". Staff check the kill, then the bounty is theirs.", "color": "yellow"}),
        f"scoreboard players set #phase {OBJ} 1",
        f"function {NS}:omens/end",
    )
    f[f"{hu}/died.mcfunction"] = lines(
        "# As the hunted player, who died, not to a player (a player's kill ends the hunt first).",
        "tellraw @a " + text(head("hunted", "red"), TARGET,
                             {"text": " died, but not to a player. The hunt is over.", "color": "gray"}),
        f"function {NS}:omens/end",
    )
    f[f"{hu}/left.mcfunction"] = lines(
        "tellraw @a " + text(head("hunted", "red"), TARGET, {"text": " left. The hunt is over.", "color": "gray"}),
        f"function {NS}:omens/end",
    )
    f[f"{hu}/survived.mcfunction"] = lines(
        "tellraw @a " + text(head("hunted", "red"), TARGET,
                             {"text": f" survived {HUNT_MINUTES} minutes. The hunt is over.", "color": "yellow"}),
        f"function {NS}:omens/end",
    )

    # ---- the end
    f[f"{FN}/interrupted.mcfunction"] = lines(
        "# An event started (or the season was locked) while an omen was on: the event takes over. A Meteor's",
        "# drop carries on: drops.py's own rules apply to it.",
        f"execute unless score #state {OBJ} matches {STATES['meteor']} run tellraw @a " + text(
            {"text": "An event is starting, so the omen is over.", "color": "gray"}),
        f"function {NS}:omens/end",
    )
    f[f"{FN}/end.mcfunction"] = lines(
        "# Ends whatever omen is on, putting back what it changed.",
        f"execute if score #state {OBJ} matches {STATES['blood_moon']} run function {NS}:omens/blood_moon/calm",
        f"execute if score #state {OBJ} matches {STATES['truce']} run function {NS}:omens/truce/restore",
        f"execute if score #state {OBJ} matches {STATES['hunted']} run function {NS}:omens/hunted/over",
        "scoreboard players reset * om.hunt",
        f"bossbar remove {BAR}",
        f"scoreboard players set #state {OBJ} 0",
        f"scoreboard players set #phase {OBJ} 0",
        f"scoreboard players set #timer {OBJ} 0",
        f"data remove storage {STORE} target",
        f"data remove storage {STORE} hunt",
        f"data remove storage {STORE} spots",
    )

    # ---- staff
    busy = f"execute if score #state {OBJ} matches 1.. run " + refuse(
        f"An omen is on already. /function {NS}:omens/stop ends it.")
    f[f"{FN}/start/blood_moon.mcfunction"] = lines(
        "# Staff: a Blood Moon at the next nightfall, whoever is online. It doesn't use up tonight's omen.",
        busy,
        f"execute store result score #r {OBJ} run function {NS}:omens/blood_moon/begin",
        f"execute unless score #r {OBJ} matches 1 run " + refuse("The game is on Peaceful: no mobs to rouse."),
        say({"text": "Blood Moon: it rises at the next nightfall.", "color": "green"}),
    )
    f[f"{FN}/start/truce.mcfunction"] = lines(
        "# Staff: a Truce Hour now. It doesn't use up tonight's omen.",
        busy,
        f"execute store result score #r {OBJ} run function {NS}:omens/truce/begin",
        f"execute unless score #r {OBJ} matches 1 run " + refuse("PvP is off already."),
    )
    f[f"{FN}/hunt.mcfunction"] = lines(
        f"# Staff, macro {{name:\"Alex\"}}: Alex is hunted for {HUNT_MINUTES} minutes, whatever their streak.",
        busy,
        f"$execute unless entity @a[name=$(name),gamemode=survival,tag=!{ARENA_TAG}] run " + refuse(
            "$(name) isn't online in survival (or is in the arena)."),
        f"$data modify storage {STORE} target set value {{name:\"$(name)\"}}",
        f"$function {NS}:omens/hunted/on {{name:\"$(name)\"}}",
    )
    f[f"{FN}/stop.mcfunction"] = lines(
        "# Staff: ends the omen now. A Meteor's drop goes on: /function monkey:drops/stop ends that.",
        f"execute unless score #state {OBJ} matches 1.. run " + refuse("No omen is on."),
        f"execute unless score #state {OBJ} matches {STATES['meteor']} run tellraw @a " + text(
            {"text": "Staff called the omen off.", "color": "gray"}),
        f"function {NS}:omens/end",
        say({"text": "Omen stopped.", "color": "green"}),
    )
    f[f"{FN}/min.mcfunction"] = lines(
        f"$scoreboard players set #min {OBJ} $(players)",
        say({"text": "An evening's omen now needs ", "color": "green"}, score("#min", "aqua"),
            {"text": " survival players online.", "color": "green"}),
    )
    f[f"{FN}/on.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 1",
        say({"text": "Automatic omens are on.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 0",
        say({"text": "Automatic omens are off until ", "color": "yellow"},
            {"text": f"/function {NS}:omens/on", "color": "aqua"}),
    )
    f[f"{FN}/status.mcfunction"] = lines(
        f"execute store result score #online {OBJ} if entity @a[gamemode=survival]",
        say({"text": "Omens: ", "color": "gold"},
            {"text": "on now ", "color": "gray"}, score("#state"),
            {"text": " (0 none, " + ", ".join(f"{n} {NAMES[o]}" for o, n in STATES.items()) + "), ",
             "color": "gray"},
            {"text": "seconds left ", "color": "gray"}, score("#timer"),
            {"text": ", automatic on ", "color": "gray"}, score("#auto"),
            {"text": ", needs ", "color": "gray"}, score("#min"),
            {"text": " online (now ", "color": "gray"}, score("#online"),
            {"text": "), last evening with one ", "color": "gray"}, score("#night")),
        f"execute if score #state {OBJ} matches {STATES['hunted']} run " + say(
            {"text": "Hunted: ", "color": "gray"}, TARGET),
    )
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box."]
    out.append(say({"text": "Omen commands (docs/ADMIN.md):", "color": "gold"}))
    for cmd, note in HELP:
        path = cmd.split(" ")[0]
        assert f"{FN}/{path}.mcfunction" in files, path
        full = f"/function {NS}:omens/{cmd}"
        out.append(say({"text": f" {cmd}", "color": "aqua",
                        "click_event": {"action": "suggest_command", "command": full}},
                       {"text": f"  {note}", "color": "dark_gray"}))
    out.append(say({"text": " A Meteor by hand: /function monkey:drops/start", "color": "dark_gray"}))
    return lines(*out)


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def show_plan(world: Path, when: dt.datetime) -> int:
    board = saved_world.scoreboard(world)
    secret = key(board.scores if board else {})
    week = season_calendar.week_at(when)
    if secret is None:
        print("no omen key saved in this world yet (the monkey-omens pack makes one when it loads): no omens")
        return 1
    if week < 1:
        print(f"season week {week}: omens start in week 1")
        return 0
    print(f"season week {week}:")
    for evening in plan(secret, week):
        print(f"  {evening.start:%a %d %b} from {evening.start:%H:%M} Pacific: "
              + ", then ".join(NAMES[o] for o in evening.order))
    return 0


meaning = server.coded(f"function {NS}:omens/try", TRY_CODES)   # the timer's log line: the try's code in words


def send(rcon, world: Path, when: dt.datetime, log=print) -> int:
    """Sends commands(world, when). Outside an evening's hours there are none and nothing is logged (it runs
    every 10 minutes); a server that isn't running is skipped. The try waits for the storage: if a command
    before it fails, it isn't sent."""
    out = commands(world, when)
    if not out:
        return 0
    return server.send_if_running(rcon, out, log, describe=meaning, stop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Omens: the week's plan, the timer's commands, the data pack.")
    sub = ap.add_subparsers(dest="command", required=True)
    server.job_subcommands(sub, "sends them to the running server (deploy/monkey-omens.sh, every 10 minutes)",
                           world=True, others=[("plan", "this week's evenings and omens (spoils the surprise)")])
    args = ap.parse_args(argv)
    if args.command == "plan":
        return show_plan(args.world, server.job_time(args))
    return server.run_job(args, lambda when: commands(args.world, when),
                          lambda rcon, when: send(rcon, args.world, when))


if __name__ == "__main__":
    sys.exit(main())
