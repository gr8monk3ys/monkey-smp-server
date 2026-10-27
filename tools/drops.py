"""Supply drops: on weeknight evenings, once enough players are online, chests land outside every territory.

    python tools/drops.py spots WORLD [--at TIME]      the spots a drop would try now, and why (changes nothing)
    python tools/drops.py commands WORLD [--at TIME]   the RCON commands for now (deploy/realms-drops.sh)
    python tools/datapacks.py                          regenerates the realms-drops data pack (with the others)

When: Monday to Thursday, 6 to 10 PM Pacific, from Season I's first week (NIGHTS, HOURS, FIRST_NIGHT).
deploy/realms-drops.sh sends `commands` every 10 minutes; outside those hours there are none. The pack starts
the night's drop the first time it is asked while MIN_PLAYERS or more are online in survival (staff change it
in game: `function realms:drops/min {players:N}`), no drop ran that night, and no event is on (the arena, a
raid, Anarchy, the season lock). One drop a night at most.

Where: Minecraft can't see claims, so this script picks the spots, from the files the server saves (as it
autosaves, every 5 to 10 minutes, and when it stops), never over RCON:
  data/openpartiesandclaims/player-claims/*.nbt                     every claimed chunk (the spawn claim too)
  dimensions/minecraft/overworld/data/minecraft/world_border.dat     the Overworld's border
A spot is the middle of an Overworld chunk in the newest border ring (between the last border act's size and
the border now, docs/SEASONS.md; before the first act, anywhere past SPAWN_CLEAR blocks from spawn),
BORDER_MARGIN blocks inside the border, and at least CLAIM_GAP chunks from every claimed chunk, so no
territory is touched (rules 34, 37 and 39). The spots are drawn at random, seeded by the night and the
10-minute slot, so a retry draws new ones. The pack then checks the ground at each in turn and takes the first
dry, natural one (grass, dirt, sand, stone: not water, not anyone's build).

What players see: a chat announcement with the coordinates and a boss bar counting down COUNTDOWN seconds,
then 1 chest for every MIN_PLAYERS online (at most MAX_CHESTS) with modest supplies (LOOT: food, iron,
arrows, wood; nothing Strength, no netherite, diamonds or emeralds, nothing the bans cover, so the drop
never beats progression or what players trade). The chests despawn after DESPAWN seconds with whatever
is left in them; an emptied chest goes at once, and the drop ends when every chest is empty or broken.

The data pack (package/realms/datapacks/realms-drops/, generated: edit this file, not it) has the staff
commands too (docs/ADMIN.md, "Supply drops"): a drop now at coordinates or where you stand, stop, on/off.
Stdlib only plus tools/map_border.py, and Python 3.10 or newer, so the VPS runs it straight from the checkout.
"""
import argparse
import datetime as dt
import gzip
import json
import random
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import map_border
import rcon as server
from datapacks import NS, function_tag, lines, mcmeta, refuse, say, text
from events import STATE
from repo import Repo

DATAPACK = "realms-drops"
FN = f"data/{NS}/function/drops"
STORE = f"{NS}:drops"
LOOT_TABLE = f"{NS}:drops/supply"
BAR = f"{NS}:drop"
OBJ = "dr"

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)
PACIFIC = ZoneInfo("America/Los_Angeles")
NIGHTS = (0, 1, 2, 3)       # Monday to Thursday (Saturday is event night)
HOURS = (18, 22)            # from 6 PM up to 10 PM Pacific
FIRST_NIGHT = dt.date(2026, 11, 23)   # Monday of Season I's week 1 (tools/challenges.py WEEK_ONE)
SLOT_MINUTES = 10           # how often deploy/realms-drops.timer asks

MIN_PLAYERS = 4             # survival players online for the weeknight drop, and for each further chest
MAX_CHESTS = 3
COUNTDOWN = 10 * 60         # announced this long before it lands (docs/SEASONS.md: 10 minutes ahead)
DESPAWN = 20 * 60           # the chests go this long after landing
WARN_AT = (300, 60)         # seconds left in the countdown when chat is reminded

ACTS = (2500, 4000, 6000)   # the border's sizes through a season (docs/SEASONS.md, the acts)
SPAWN_CLEAR = 400           # no drop this close to spawn (the border's centre), in blocks either way
BORDER_MARGIN = 64          # nor this close to the border
CLAIM_GAP = 6               # chunks between a drop's chunk and the nearest claimed chunk (96 blocks and more)
SPOT_GAP = 8                # chunks between two spots offered the same night
SPOTS = 6                   # spots offered each time; the pack tries them in order
DRAWS = 5000                # random chunks looked at to find them
OVERWORLD = "minecraft:overworld"
OPAC_CLAIMS = Path("data") / "openpartiesandclaims" / "player-claims"

# Chest offsets from the drop's middle (x, z), one per chest. Never side by side, so they never join.
CHEST_AT = ((0, 0), (3, 2), (-3, 2))
REACH = 4                   # blocks around the middle kept loaded while a drop is on (covers CHEST_AT)

# ---------------------------------------------------------------- the loot: edit here
#
# (pool, item, weight, min, max). Each chest rolls every pool: food 3 or 4 times, supplies 2 or 3 times and
# one extra. Modest on purpose: no Strength items, no netherite, diamonds or emeralds (what players
# trade with), no golden apples, potions, enchantments or anything the bans cover.
LOOT = [
    ("food", "bread", 3, 4, 8),
    ("food", "cooked_beef", 3, 3, 6),
    ("food", "baked_potato", 2, 4, 8),
    ("food", "golden_carrot", 1, 2, 4),
    ("supplies", "iron_ingot", 2, 2, 5),
    ("supplies", "coal", 3, 6, 12),
    ("supplies", "arrow", 2, 8, 16),
    ("supplies", "torch", 2, 8, 16),
    ("supplies", "oak_log", 2, 8, 16),
    ("supplies", "string", 1, 2, 6),
    ("supplies", "leather", 1, 2, 5),
    ("supplies", "redstone", 1, 4, 10),
    ("extra", "experience_bottle", 3, 2, 5),
    ("extra", "lapis_lazuli", 2, 4, 8),
    ("extra", "name_tag", 1, 1, 1),
    ("extra", "saddle", 1, 1, 1),
]
ROLLS = {"food": (3, 4), "supplies": (2, 3), "extra": (1, 1)}

# What a drop may sit on: the natural ground of the Overworld's surface, so never on someone's build.
# (26.3's substrate_overworld is dirt, grass blocks, podzol, mycelium, mud and moss.)
GROUND = ["#minecraft:substrate_overworld", "#minecraft:sand", "#minecraft:terracotta",
          "#minecraft:base_stone_overworld", "minecraft:gravel", "minecraft:clay", "minecraft:snow_block",
          "minecraft:sandstone", "minecraft:red_sandstone", "minecraft:calcite"]
# What a chest may replace: air and the plants and snow that grow on that ground by themselves.
OPEN = ["minecraft:air", "minecraft:cave_air", "minecraft:short_grass", "minecraft:fern", "minecraft:dead_bush",
        "minecraft:short_dry_grass", "minecraft:snow", "#minecraft:small_flowers"]
OPTIONAL = {"minecraft:short_dry_grass"}   # newer blocks: the tag still loads on a Minecraft without them

# What `function realms:drops/try` returns, for the timer's log (meaning()).
TRY_CODES = {
    1: "started: checking the ground at the spots",
    10: "automatic drops are off (function realms:drops/on)",
    11: "a drop is already on",
    12: "tonight's drop already happened",
    13: "an event is on (the arena, a raid, Anarchy or the season lock)",
    14: "fewer survival players online than the minimum",
    15: "no spots were sent",
}

HELP = [
    ("start {x:0,z:0}", "a drop at those coordinates, now (any number online)"),
    ("here", "a drop where you stand, now"),
    ("stop", "ends the drop now; its chests go"),
    ("status", "what's on, and the settings"),
    ("min {players:4}", "survival players needed for the weeknight drop"),
    ("off", "no weeknight drops until on"),
    ("on", "weeknight drops again"),
]


# ---------------------------------------------------------------- when


def parse_time(value: str) -> dt.datetime:
    when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def night_of(when: dt.datetime) -> int | None:
    """The drop night `when` falls in, as YYYYMMDD (its Pacific date), or None outside drop hours."""
    local = when.astimezone(PACIFIC)
    if local.date() < FIRST_NIGHT or local.weekday() not in NIGHTS or not HOURS[0] <= local.hour < HOURS[1]:
        return None
    return int(local.strftime("%Y%m%d"))


def slot_of(when: dt.datetime) -> str:
    """The 10-minute slot, which seeds the draw: the same slot draws the same spots."""
    local = when.astimezone(PACIFIC)
    return f"{local:%Y%m%d-%H}{local.minute // SLOT_MINUTES}"


# ---------------------------------------------------------------- where


def load_nbt(path: Path) -> dict:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if not data or data[0] != 10:
        raise ValueError(f"{path}: not an NBT compound")
    _, pos = map_border._read(data, 1, 8)   # the root's name
    root, _ = map_border._read(data, pos, 10)
    return root


def claimed_chunks(world: Path) -> set[tuple[int, int]]:
    """Every claimed chunk in the Overworld, whoever claimed it (players, parties' members, the server).
    Open Parties and Claims saves a player's claims as dimensions > claims > positions: [{x, z}] (chunks)."""
    out: set[tuple[int, int]] = set()
    folder = world / OPAC_CLAIMS
    for path in sorted(folder.glob("*.nbt")) if folder.is_dir() else []:
        dim = load_nbt(path).get("dimensions", {}).get(OVERWORLD, {})
        for claim in dim.get("claims", []):
            out.update((int(p["x"]), int(p["z"])) for p in claim.get("positions", []))
    return out


def border_now(world: Path) -> map_border.Border | None:
    """The Overworld border as it is now (a growing border counts at its current size, a shrinking one at its
    target), or None when the world has none saved."""
    path = world / "dimensions" / "minecraft" / "overworld" / "data" / "minecraft" / "world_border.dat"
    if not path.is_file():
        return None
    data = load_nbt(path)["data"]
    size = min(data["size"], data.get("lerp_target", data["size"]))
    if size >= map_border.NO_BORDER:
        return None
    return map_border.Border(data["center_x"], data["center_z"], size)


def ring(border: map_border.Border) -> tuple[float, float]:
    """(inner, outer): how far from the border's centre (blocks, either axis) a drop may be."""
    before = [size for size in ACTS if size < border.size]
    inner = max(SPAWN_CLEAR, before[-1] / 2 if before else 0)
    return inner, border.size / 2 - BORDER_MARGIN


def spots(world: Path, seed: str, count: int = SPOTS) -> list[tuple[int, int]]:
    """Up to `count` drop spots (block x, z: the middle of a chunk), the same for the same seed and world."""
    border = border_now(world)
    if border is None:
        return []
    inner, outer = ring(border)
    if outer <= inner:
        return []
    claims = claimed_chunks(world)
    rng = random.Random(seed)
    cx, cz = border.center_x, border.center_z
    lo_x, hi_x = int((cx - outer) // 16), int((cx + outer) // 16)
    lo_z, hi_z = int((cz - outer) // 16), int((cz + outer) // 16)
    picked: list[tuple[int, int]] = []
    for _ in range(DRAWS):
        if len(picked) >= count:
            break
        chunk = rng.randint(lo_x, hi_x), rng.randint(lo_z, hi_z)
        x, z = chunk[0] * 16 + 8, chunk[1] * 16 + 8
        if not inner <= max(abs(x - cx), abs(z - cz)) <= outer:
            continue
        if any((chunk[0] + dx, chunk[1] + dz) in claims
               for dx in range(-CLAIM_GAP, CLAIM_GAP + 1) for dz in range(-CLAIM_GAP, CLAIM_GAP + 1)):
            continue
        if any(max(abs(chunk[0] - (px - 8) // 16), abs(chunk[1] - (pz - 8) // 16)) < SPOT_GAP for px, pz in picked):
            continue
        picked.append((x, z))
    return picked


def commands(world: Path, when: dt.datetime) -> list[str]:
    """What deploy/realms-drops.sh sends: nothing outside drop hours, else the spots and the try."""
    night = night_of(when)
    if night is None:
        return []
    found = spots(world, slot_of(when))
    if not found:
        return []
    listed = ",".join(f"{{x:{x},z:{z}}}" for x, z in found)
    return [f"data modify storage {STORE} spots set value [{listed}]",
            f"function {NS}:drops/try {{night:{night}}}"]


# ---------------------------------------------------------------- the data pack


def spot(key: str, color: str = "aqua") -> dict:
    return {"nbt": f"spot.{key}", "storage": STORE, "color": color}


def score(holder: str, color: str = "white") -> dict:
    return {"score": {"name": holder, "objective": OBJ}, "color": color}


HEAD = {"text": "Supply drop: ", "color": "gold", "bold": True}
AT_XZ = [spot("x"), {"text": ", ", "color": "aqua"}, spot("z")]
AT_XYZ = [spot("x"), {"text": " ", "color": "aqua"}, spot("y"), {"text": " ", "color": "aqua"}, spot("z")]
EVENTS_ON = [f"#arena {STATE} matches 1", f"#raid {STATE} matches 1..", f"#anarchy {STATE} matches 1..",
             f"#season_locked {STATE} matches 1"]
CHEST = "minecraft:chest"
CHEST_NAME = "Supply drop"
LABEL = "dr.label"


def loot_table() -> dict:
    pools = []
    for pool, (lo, hi) in ROLLS.items():
        entries = []
        for p, name, weight, a, b in LOOT:
            if p != pool:
                continue
            entry = {"type": "minecraft:item", "name": f"minecraft:{name}", "weight": weight}
            if b > 1:   # 26.3's form: one "modifier" (older packs had a "functions" list)
                entry["modifier"] = {"type": "minecraft:set_count",
                                     "count": {"type": "minecraft:uniform", "min": a, "max": b}}
            entries.append(entry)
        rolls = lo if lo == hi else {"type": "minecraft:uniform", "min": lo, "max": hi}
        pools.append({"rolls": rolls, "entries": entries})
    return {"type": "minecraft:chest", "pools": pools}


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP supply drops (generated by tools/drops.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:drops/load")
    f[f"data/{NS}/loot_table/drops/supply.json"] = json.dumps(loot_table(), indent=2)
    f[f"data/{NS}/tags/block/drops/ground.json"] = json.dumps({"values": GROUND}, indent=2)
    f[f"data/{NS}/tags/block/drops/open.json"] = json.dumps(
        {"values": [{"id": v, "required": False} if v in OPTIONAL else v for v in OPEN]}, indent=2)
    ground, open_ = f"#{NS}:drops/ground", f"#{NS}:drops/open"
    fits = f"if block ~ ~-1 ~ {ground} if block ~ ~ ~ {open_}"

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/drops.py. Scores and storage are kept across restarts.",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard players set #60 {OBJ} 60",
        f"execute unless score #min {OBJ} matches 1.. run scoreboard players set #min {OBJ} {MIN_PLAYERS}",
        f"execute unless score #auto {OBJ} matches 0.. run scoreboard players set #auto {OBJ} 1",
        f"execute unless score #state {OBJ} matches 0.. run scoreboard players set #state {OBJ} 0",
        f"schedule function {NS}:drops/second 20t replace",
        "# Checking the ground when the server stopped: check again (a schedule may not outlast a restart).",
        f"execute if score #state {OBJ} matches 1 run schedule function {NS}:drops/check 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:drops/second 20t replace",
        f"execute if score #state {OBJ} matches 2 run function {NS}:drops/countdown",
        f"execute if score #state {OBJ} matches 3 run function {NS}:drops/landed",
    )

    # ---- starting
    f[f"{FN}/try.mcfunction"] = lines(
        "# The weeknight drop: deploy/realms-drops.sh calls this every 10 minutes in drop hours, after putting",
        f"# the spots in storage {STORE} spots. Returns why it didn't start (tools/drops.py TRY_CODES).",
        f"execute unless score #auto {OBJ} matches 1 run return 10",
        f"execute if score #state {OBJ} matches 1.. run return 11",
        f"$execute if score #night {OBJ} matches $(night) run return 12",
        *(f"execute if score {cond} run return 13" for cond in EVENTS_ON),
        f"execute store result score #online {OBJ} if entity @a[gamemode=survival]",
        f"execute if score #online {OBJ} < #min {OBJ} run return 14",
        f"execute unless data storage {STORE} spots[0] run return 15",
        f"$data modify storage {STORE} night set value $(night)",
        f"function {NS}:drops/locate",
        "return 1",
    )
    f[f"{FN}/start.mcfunction"] = lines(
        "# Staff: a drop at x, z now, whoever is online. It still checks the ground there.",
        f"execute if score #state {OBJ} matches 1.. run " + refuse(
            f"A supply drop is on already. /function {NS}:drops/stop ends it."),
        f"$data modify storage {STORE} spots set value [{{x:$(x),z:$(z)}}]",
        f"execute store result score #online {OBJ} if entity @a[gamemode=survival]",
        "# A drop by hand doesn't use up tonight's: keep the night as it was.",
        f"data modify storage {STORE} night set value 0",
        f"execute store result storage {STORE} night int 1 run scoreboard players get #night {OBJ}",
        f"function {NS}:drops/locate",
        say({"text": "Checking the ground there; the announcement follows if it's dry land.", "color": "gray"}),
    )
    f[f"{FN}/here.mcfunction"] = lines(
        "# Staff: a drop where you stand (in the Overworld: Nether or End coordinates would put it elsewhere).",
        f"execute unless dimension {OVERWORLD} run " + refuse(
            f"Supply drops land in the Overworld: stand there, or use /function {NS}:drops/start {{x:0,z:0}}."),
        f"execute store result storage {STORE} here.x int 1 run data get entity @s Pos[0]",
        f"execute store result storage {STORE} here.z int 1 run data get entity @s Pos[2]",
        f"function {NS}:drops/start with storage {STORE} here",
    )

    # ---- finding dry, natural ground at a spot
    f[f"{FN}/locate.mcfunction"] = lines(
        "# Takes the next spot, loads the chunks around it and checks the ground in a second.",
        f"scoreboard players set #state {OBJ} 1",
        f"scoreboard players set #wait {OBJ} 0",
        f"data modify storage {STORE} spot set from storage {STORE} spots[0]",
        f"data remove storage {STORE} spots[0]",
        f"execute store result score #x {OBJ} run data get storage {STORE} spot.x",
        f"execute store result score #z {OBJ} run data get storage {STORE} spot.z",
        f"execute store result storage {STORE} spot.x0 int 1 run scoreboard players remove #x {OBJ} {REACH}",
        f"execute store result storage {STORE} spot.z0 int 1 run scoreboard players remove #z {OBJ} {REACH}",
        f"execute store result storage {STORE} spot.x1 int 1 run scoreboard players add #x {OBJ} {2 * REACH}",
        f"execute store result storage {STORE} spot.z1 int 1 run scoreboard players add #z {OBJ} {2 * REACH}",
        f"function {NS}:drops/hold with storage {STORE} spot",
        f"schedule function {NS}:drops/check 20t replace",
    )
    # forceload works in the dimension it runs in, and staff may start or stop a drop from the Nether or the
    # End: pinned to the Overworld, where the drop is, so the chunks loaded are the ones released.
    f[f"{FN}/hold.mcfunction"] = lines(f"$execute in {OVERWORLD} run forceload add $(x0) $(z0) $(x1) $(z1)")
    f[f"{FN}/release.mcfunction"] = lines(f"$execute in {OVERWORLD} run forceload remove $(x0) $(z0) $(x1) $(z1)")
    f[f"{FN}/check.mcfunction"] = lines(
        f"execute unless score #state {OBJ} matches 1 run return 0",
        f"function {NS}:drops/check_at with storage {STORE} spot",
    )
    f[f"{FN}/check_at.mcfunction"] = lines(
        f"$execute unless loaded $(x) 0 $(z) run return run function {NS}:drops/wait",
        f"$execute in minecraft:overworld positioned $(x) 0 $(z) positioned over motion_blocking_no_leaves {fits} "
        f"run return run function {NS}:drops/found",
        "# Water, a build or anything else: the next spot.",
        f"function {NS}:drops/next",
    )
    f[f"{FN}/wait.mcfunction"] = lines(
        f"scoreboard players add #wait {OBJ} 1",
        f"execute if score #wait {OBJ} matches ..10 run return run schedule function {NS}:drops/check 20t replace",
        f"function {NS}:drops/next",
    )
    f[f"{FN}/next.mcfunction"] = lines(
        f"function {NS}:drops/release with storage {STORE} spot",
        f"execute if data storage {STORE} spots[0] run return run function {NS}:drops/locate",
        "# None was dry land: no drop this time (the timer sends new spots in 10 minutes).",
        f"scoreboard players set #state {OBJ} 0",
        f"data remove storage {STORE} spot",
    )
    f[f"{FN}/found.mcfunction"] = lines(
        "# Run at the spot's surface: announce it, count down.",
        "summon minecraft:marker ~ ~ ~ {Tags:[\"dr.spot\"]}",
        f"execute store result storage {STORE} spot.y int 1 run data get entity @e[type=minecraft:marker,"
        "tag=dr.spot,limit=1] Pos[1]",
        f"execute store result score #night {OBJ} run data get storage {STORE} night",
        f"scoreboard players operation #chests {OBJ} = #online {OBJ}",
        f"scoreboard players operation #chests {OBJ} /= #min {OBJ}",
        f"execute if score #chests {OBJ} matches ..0 run scoreboard players set #chests {OBJ} 1",
        f"execute if score #chests {OBJ} matches {MAX_CHESTS + 1}.. run scoreboard players set #chests {OBJ} "
        f"{MAX_CHESTS}",
        f"scoreboard players set #state {OBJ} 2",
        f"scoreboard players set #timer {OBJ} {COUNTDOWN}",
        f"bossbar add {BAR} " + text({"text": "Supply drop", "color": "gold"}),
        f"bossbar set {BAR} color yellow",
        f"bossbar set {BAR} max {COUNTDOWN}",
        f"bossbar set {BAR} value {COUNTDOWN}",
        f"bossbar set {BAR} players @a",
        f"bossbar set {BAR} visible true",
        "tellraw @a " + text("", HEAD, {"text": "it lands at ", "color": "yellow"}, *AT_XYZ,
                             {"text": f" in {COUNTDOWN // 60} minutes, with ", "color": "yellow"},
                             score("#chests", "aqua"), {"text": " chest(s) of supplies. First come, first served; "
                                                         "the usual rules apply out there.", "color": "yellow"}),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 0.7",
    )

    # ---- the countdown and the landing
    def bar_name(label: str, color: str, place: list) -> str:
        return f"bossbar set {BAR} name " + text({"text": "Supply drop at ", "color": color}, *place,
                                                 {"text": f": {label} ", "color": color}, score("#mins"),
                                                 {"text": " min", "color": color})

    minutes = [f"scoreboard players operation #mins {OBJ} = #timer {OBJ}",
               f"scoreboard players add #mins {OBJ} 59",
               f"scoreboard players operation #mins {OBJ} /= #60 {OBJ}",
               f"execute store result bossbar {BAR} value run scoreboard players get #timer {OBJ}",
               f"bossbar set {BAR} players @a"]
    f[f"{FN}/countdown.mcfunction"] = lines(
        f"scoreboard players remove #timer {OBJ} 1",
        *minutes,
        bar_name("lands in", "yellow", AT_XZ),
        *(f"execute if score #timer {OBJ} matches {s} run tellraw @a " + text(
            "", HEAD, {"text": f"{s // 60} minute{'s' if s > 60 else ''} until it lands at ", "color": "yellow"},
            *AT_XYZ, {"text": ".", "color": "yellow"}) for s in WARN_AT),
        f"execute if score #timer {OBJ} matches ..0 run function {NS}:drops/land",
    )
    place = [f"execute if score #chests {OBJ} matches {k + 1}.. positioned ~{dx} ~ ~{dz} positioned over "
             f"motion_blocking_no_leaves {fits} run function {NS}:drops/place"
             for k, (dx, dz) in enumerate(CHEST_AT)]
    f[f"{FN}/land.mcfunction"] = lines(
        f"scoreboard players set #state {OBJ} 3",
        f"scoreboard players set #timer {OBJ} {DESPAWN}",
        f"execute at @e[type=minecraft:marker,tag=dr.spot,limit=1] run function {NS}:drops/chests",
        "# Built over in the last 10 minutes: one chest on top, into air only.",
        f"execute unless entity @e[type=minecraft:marker,tag=dr.chest] at @e[type=minecraft:marker,tag=dr.spot,"
        f"limit=1] positioned over motion_blocking_no_leaves if block ~ ~ ~ #{NS}:drops/open run function "
        f"{NS}:drops/place",
        f"execute unless entity @e[type=minecraft:marker,tag=dr.chest] run return run function {NS}:drops/blocked",
        f"execute at @e[type=minecraft:marker,tag=dr.spot,limit=1] positioned over motion_blocking_no_leaves run "
        f"summon minecraft:text_display ~ ~1.8 ~ {{Tags:[\"{LABEL}\"],billboard:\"center\","
        f"text:{{text:\"{CHEST_NAME}\",color:\"gold\",bold:true}}}}",
        f"bossbar set {BAR} color red",
        f"bossbar set {BAR} max {DESPAWN}",
        "tellraw @a " + text("", HEAD, {"text": "it has landed at ", "color": "yellow"}, *AT_XYZ,
                             {"text": f". The chests despawn in {DESPAWN // 60} minutes, with whatever is still in "
                                      "them.", "color": "yellow"}),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1.2",
    )
    f[f"{FN}/chests.mcfunction"] = lines("# Run at the drop's middle.", *place)
    f[f"{FN}/place.mcfunction"] = lines(
        "# Filled now rather than given a loot table to roll when opened: Loot Restock (2.8.0) remembers every",
        "# chest that is opened with a loot table and refills it a week later, which would make a drop's spot",
        "# a weekly supply drop.",
        f"setblock ~ ~ ~ {CHEST}{{CustomName:\"{CHEST_NAME}\"}}",
        f"loot insert ~ ~ ~ loot {LOOT_TABLE}",
        "summon minecraft:marker ~ ~ ~ {Tags:[\"dr.chest\"]}",
        "particle minecraft:end_rod ~ ~1 ~ 0.3 1.5 0.3 0.05 40 force",
    )
    f[f"{FN}/landed.mcfunction"] = lines(
        f"scoreboard players remove #timer {OBJ} 1",
        *minutes,
        bar_name("despawns in", "red", AT_XZ),
        "# A broken chest is done; an emptied one goes at once.",
        f"execute as @e[type=minecraft:marker,tag=dr.chest] at @s unless block ~ ~ ~ {CHEST} run kill @s",
        "# (A drop that landed before 2.8.0 keeps its loot table, and no items, until someone opens it.)",
        f"execute as @e[type=minecraft:marker,tag=dr.chest] at @s unless data block ~ ~ ~ LootTable unless data "
        f"block ~ ~ ~ Items[0] run function {NS}:drops/emptied",
        f"execute unless entity @e[type=minecraft:marker,tag=dr.chest] run return run function {NS}:drops/looted",
        f"execute if score #timer {OBJ} matches 300 run tellraw @a " + text(
            "", HEAD, {"text": "5 minutes until the chests at ", "color": "yellow"}, *AT_XZ,
            {"text": " despawn.", "color": "yellow"}),
        f"execute if score #timer {OBJ} matches ..0 run function {NS}:drops/expire",
    )
    f[f"{FN}/emptied.mcfunction"] = lines(
        "# As a chest's marker, at the chest: it is empty, so it goes (nothing is lost).",
        "setblock ~ ~ ~ minecraft:air",
        "particle minecraft:poof ~ ~0.5 ~ 0.3 0.3 0.3 0.02 10",
        "kill @s",
    )

    # ---- the end
    remove_chests = (f"execute as @e[type=minecraft:marker,tag=dr.chest] at @s if block ~ ~ ~ {CHEST} if data "
                     f"block ~ ~ ~ {{CustomName:\"{CHEST_NAME}\"}} run setblock ~ ~ ~ minecraft:air")
    f[f"{FN}/looted.mcfunction"] = lines(
        "tellraw @a " + text("", HEAD, {"text": "every chest at ", "color": "yellow"}, *AT_XZ,
                             {"text": " has been emptied. Until the next one.", "color": "yellow"}),
        f"function {NS}:drops/cleanup",
    )
    f[f"{FN}/expire.mcfunction"] = lines(
        "# The chests go with what's left in them (setblock clears a container it replaces: nothing drops).",
        remove_chests,
        "tellraw @a " + text("", HEAD, {"text": "the chests at ", "color": "yellow"}, *AT_XZ,
                             {"text": " have despawned.", "color": "yellow"}),
        f"function {NS}:drops/cleanup",
    )
    f[f"{FN}/blocked.mcfunction"] = lines(
        "tellraw @a " + text("", HEAD, {"text": "it couldn't land at ", "color": "yellow"}, *AT_XZ,
                             {"text": ": something was built there. No drop this time.", "color": "yellow"}),
        f"function {NS}:drops/cleanup",
    )
    f[f"{FN}/stop.mcfunction"] = lines(
        "# Staff: ends the drop now, whatever stage it is in; its chests go with what's in them.",
        f"execute unless score #state {OBJ} matches 1.. run " + refuse("No supply drop is on."),
        remove_chests,
        f"execute if score #state {OBJ} matches 2.. run tellraw @a " + text(
            "", HEAD, {"text": "staff called it off.", "color": "gray"}),
        f"function {NS}:drops/cleanup",
        say({"text": "Supply drop stopped.", "color": "green"}),
    )
    f[f"{FN}/cleanup.mcfunction"] = lines(
        "kill @e[type=minecraft:marker,tag=dr.chest]",
        f"kill @e[type=minecraft:text_display,tag={LABEL}]",
        "kill @e[type=minecraft:marker,tag=dr.spot]",
        f"execute if data storage {STORE} spot.x0 run function {NS}:drops/release with storage {STORE} spot",
        f"schedule clear {NS}:drops/check",
        f"bossbar remove {BAR}",
        f"scoreboard players set #state {OBJ} 0",
        f"scoreboard players set #timer {OBJ} 0",
        f"data remove storage {STORE} spot",
        f"data remove storage {STORE} spots",
    )

    # ---- settings
    f[f"{FN}/min.mcfunction"] = lines(
        f"$scoreboard players set #min {OBJ} $(players)",
        say({"text": "Weeknight drops now need ", "color": "green"}, score("#min", "aqua"),
            {"text": " survival players online (and that many more for each extra chest).", "color": "green"}),
    )
    f[f"{FN}/on.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 1",
        say({"text": "Weeknight supply drops are on.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        f"scoreboard players set #auto {OBJ} 0",
        say({"text": "Weeknight supply drops are off until ", "color": "yellow"},
            {"text": f"/function {NS}:drops/on", "color": "aqua"}),
    )
    f[f"{FN}/status.mcfunction"] = lines(
        f"execute store result score #online {OBJ} if entity @a[gamemode=survival]",
        say({"text": "Supply drops: ", "color": "gold"},
            {"text": "state ", "color": "gray"}, score("#state"),
            {"text": " (0 none, 1 checking the ground, 2 counting down, 3 landed), ", "color": "gray"},
            {"text": "seconds left ", "color": "gray"}, score("#timer"),
            {"text": ", weeknight drops on ", "color": "gray"}, score("#auto"),
            {"text": ", needs ", "color": "gray"}, score("#min"),
            {"text": " online (now ", "color": "gray"}, score("#online"),
            {"text": "), last night with a drop ", "color": "gray"}, score("#night")),
        f"execute if score #state {OBJ} matches 2.. run " + say({"text": "At ", "color": "gray"}, *AT_XYZ),
    )
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box."]
    out.append(say({"text": "Supply drop commands (docs/ADMIN.md):", "color": "gold"}))
    for cmd, note in HELP:
        path = cmd.split(" ")[0]
        assert f"{FN}/{path}.mcfunction" in files, path
        full = f"/function {NS}:drops/{cmd}"
        out.append(say({"text": f" {cmd}", "color": "aqua",
                        "click_event": {"action": "suggest_command", "command": full}},
                       {"text": f"  {note}", "color": "dark_gray"}))
    return lines(*out)


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.realms / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def show_spots(world: Path, when: dt.datetime) -> int:
    night = night_of(when)
    local = when.astimezone(PACIFIC)
    print(f"{local:%a %d %b %Y %H:%M} Pacific: " + (f"drop night {night}" if night else
          "outside drop hours (Monday to Thursday, 6 to 10 PM Pacific, from Season I week 1)"))
    border = border_now(world)
    if border is None:
        print("no Overworld border saved in this world: no spots")
        return 1
    inner, outer = ring(border)
    print(f"{border.describe()}; drops between {inner:g} and {outer:g} blocks from its centre, either axis")
    print(f"claimed chunks in the Overworld: {len(claimed_chunks(world))}; a drop keeps {CLAIM_GAP} chunks away")
    found = spots(world, slot_of(when))
    for x, z in found:
        print(f"  {x} {z}")
    if not found:
        print("no spot found")
    return 0 if found else 1


def meaning(command: str, answer: str) -> str:
    """The timer's log line for one command's answer: the try's return code in words."""
    if not command.startswith(f"function {NS}:drops/try"):
        said = command[:60] if command.startswith("function ") else "spots sent"
        return f"{said}: {answer or 'ok'}"
    m = re.search(r" returned (\d+)$", answer)
    return f"{command}: {TRY_CODES.get(int(m[1]), answer) if m else answer or 'ok'}"


def send(rcon, world: Path, when: dt.datetime, log=print) -> int:
    """Sends commands(world, when). Outside drop hours there are none, and nothing is logged (it runs every 10
    minutes); a server that isn't running is skipped. The try waits for the spots: if they don't arrive, it isn't
    sent (it would try last night's)."""
    out = commands(world, when)
    if not out:
        return 0
    return server.send_if_running(rcon, out, log, describe=meaning, stop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Supply drops: the spots, the timer's commands, the data pack.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("spots", "the spots a drop would try now, and why"),
                        ("commands", "the RCON commands for now (changes nothing)"),
                        ("send", "sends them to the running server (deploy/realms-drops.sh, every 10 minutes)")):
        p = sub.add_parser(name, help=about)
        p.add_argument("world", type=Path, help="the world folder (server/world)")
        p.add_argument("--at", type=parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        if name == "send":
            p.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")
    args = ap.parse_args(argv)
    now = args.at or dt.datetime.now(UTC)
    if args.command == "spots":
        return show_spots(args.world, now)
    if args.command == "send":
        return send(server.Docker(args.docker), args.world, now)
    out = commands(args.world, now)
    if out:
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
