"""The border boss: on each Season II border act, a boss rises in the newly opened ring, for the factions to hunt.

    python tools/datapacks.py                 regenerates the monkey-boss data pack (with the others)
    python tools/boss.py spot --season 2      where each act's boss rises (the timer works it out the same way)
    python tools/boss.py status WORLD         each act's boss in the saved world: risen, slain (by whom), left

What players see: when a border act grows the border (tools/border.py), chat says the Edgewalker rises near
X, Z in RISE_SECONDS, once the border has finished growing; then it rises there, a boss bar shows its health to
players near it, and everyone is told where it is. It is a vanilla wither skeleton, twice the size, with
the armor, damage and health below (health scaled to the survival players online when it rises, between
MIN_HEALTH and MAX_HEALTH). The first player to land the killing blow gets a Server First ("Slay a border boss",
tools/firsts.py, Season II on), and every kill is announced with the killer's faction (tools/diplomacy.py's
number) and kept for the news post, the Sunday recap and the Hall of Banners. Nobody kills it within
LIFE_SECONDS: it leaves, with a message. Its gear never drops. Nothing is sold and nothing it gives helps in a
fight: a line in chat, a first and a banner in the hall.

Where: the timer picks the spot from the border's centre and the act's new width (spot(), seeded by the season
and the act, so a re-run picks the same one): INSET blocks inside the new edge, on a side and at an offset drawn
from the seed, so always in the ring the act opened. The pack puts it on the surface there (the highest block
that stops movement, as drops and outposts read the ground), keeping that one chunk loaded until it ends.

When and how often: only the border timer starts one, with `function monkey:boss/act {act:N,x:X,z:Z,delay:S}`
sent after the act is recorded (so a pack that isn't there can't hold the act back). The pack keeps the last act
it took (#act bs) and takes each act once: the act can be sent again (a retry, or staff by hand) and never makes
a second boss. Only while the switch is on (`function monkey:boss/on`, docs/SEASONS.md "Switches"; off in a new
world), from Season II (`#season rw.day` 2 or more), after the launch and before the season's lock. In Season I
nothing here runs: the border has no timed acts (tools/border.py) and the pack refuses.

The data pack (package/monkey/datapacks/monkey-boss/, generated: edit this file, not it) has the staff commands
(docs/ADMIN.md, "The border boss"). Stdlib only plus tools/saved_world.py, Python 3.10 or newer, so the VPS runs it
straight from the checkout.
"""
import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import saved_world
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, text
from events import STATE
from repo import Repo

DATAPACK = "monkey-boss"
FN = f"data/{NS}/function/boss"
STORE = f"{NS}:boss"
KEY = "boss"                # STORE's key in the namespace's command storage file
BAR = f"{NS}:boss"
OBJ = "bs"                  # #on, #act, #state (0 none, 1 waiting to rise, 2 up), #wait, #left, and scratch
ID = "bs.id"                # on the boss itself: the act it rose for (the kill advancement reads it)
TAG = "monkey.boss"
MOB = "minecraft:wither_skeleton"
NAME = "The Edgewalker"
SEASON = "#season rw.day"
LOCKED = "#season_locked"   # in events' ev.state: the season's lock

# The fight: edit here (docs/SEASONS.md, "The border boss", says the same).
BASE_HEALTH = 150           # health with nobody online ...
PER_PLAYER = 40             # ... plus this for each survival player online when it rises ...
MIN_HEALTH, MAX_HEALTH = 200, 1000   # ... kept between these (1024 is the game's cap)
ATTRIBUTES = {              # vanilla attributes, base values
    "minecraft:scale": 2.0,
    "minecraft:armor": 15,
    "minecraft:armor_toughness": 6,
    "minecraft:attack_damage": 14,
    "minecraft:knockback_resistance": 0.8,
    "minecraft:movement_speed": 0.3,
    "minecraft:follow_range": 48,
    "minecraft:step_height": 1.5,
    "minecraft:fall_damage_multiplier": 0,
}
GEAR = {"mainhand": "minecraft:diamond_sword", "head": "minecraft:diamond_helmet",
        "chest": "minecraft:diamond_chestplate"}
BAR_RANGE = 96              # players this close see its health bar
EVENT_RADIUS = BAR_RANGE    # the fight is a staff event (docs/RULES.md, rule 41) within this of the boss, while up
RISE_SECONDS = 615          # after the act: the border's 10-minute growth (border.GROW_SECONDS) and a little
LIFE_SECONDS = 90 * 60      # it leaves if nobody has killed it by then
WARN_LEFT = 10 * 60         # "leaves in 10 minutes"
INSET = 48                  # blocks inside the act's new edge

# What `function monkey:boss/act` returns (the border timer's log reads them through rcon.coded).
CODES = {
    1: "the boss rises when the border has grown",
    10: "the boss is off (function monkey:boss/on)",
    11: "not Season II or later: no boss",
    12: "the season hasn't launched",
    13: "the season is locked",
    14: "this act's boss was already taken",
    15: "a boss is already up",
}


# ---------------------------------------------------------------- where it rises


def spot(season: int, act: int, center_x: float, center_z: float, size: float) -> tuple[int, int]:
    """The block (x, z) the act's boss rises at: INSET blocks inside the edge of a border `size` wide around the
    centre, on a side and at an offset drawn from the season and act. The same every time for the same act."""
    rng = random.Random(f"monkey-boss-{season}-{act}")
    reach = size / 2 - INSET
    side = rng.randrange(4)
    along = rng.uniform(-reach, reach)
    dx, dz = ((0, -reach), (reach, 0), (0, reach), (-reach, 0))[side]
    x, z = (along, dz) if dx == 0 else (dx, along)
    return round(center_x + x), round(center_z + z)


def act_command(season: int, act: int, center_x: float, center_z: float, size: float,
                delay: int = RISE_SECONDS) -> str:
    x, z = spot(season, act, center_x, center_z, size)
    return f"function {NS}:boss/act {{act:{act},x:{x},z:{z},delay:{delay}}}"


# ---------------------------------------------------------------- the saved world


@dataclass(frozen=True)
class Outcome:
    act: int
    state: str          # "risen" (or waiting), "slain", "left", "fell"
    x: int
    z: int
    health: int
    player: str         # who slew it ("" otherwise)
    faction: int        # their faction number (0: none, or not slain)
    week: int | None    # the challenge week it ended in, or rose in while it is up


def outcomes(world: Path) -> list[Outcome]:
    """Every act's boss the saved world has a record of, by act. A file not shaped as the server saves it is a
    ValueError (saved_world's)."""
    storage = saved_world.command_storage(world, NS) or {}
    acts = storage.get(KEY, {}).get("acts", {})
    out = []
    for key, rec in (acts.items() if isinstance(acts, dict) else ()):
        if not (key.startswith("a") and key[1:].isdigit() and isinstance(rec, dict)):
            continue
        week = _num(rec, "week", -1)
        name = rec.get("name")
        out.append(Outcome(int(key[1:]), str(rec.get("state", "")), _num(rec, "x"), _num(rec, "z"), _num(rec, "hp"),
                           name if isinstance(name, str) else "", _num(rec, "faction"), week if week >= 0 else None))
    return sorted(out, key=lambda o: o.act)


def _num(rec: dict, field: str, default: int = 0) -> int:
    v = rec.get(field)
    return v if isinstance(v, int) else default


def describe(o: Outcome, names: dict[int, str]) -> str:
    """One line, plain words: what became of an act's boss."""
    faction = names.get(o.faction, f"faction {o.faction}") if o.faction else ""
    if o.state == "slain":
        by = f"{o.player or 'a player'}" + (f" ({faction})" if faction else " (in no faction)")
        return f"Act {o.act}: {NAME} was slain by {by}, near {o.x}, {o.z}."
    if o.state == "left":
        return f"Act {o.act}: {NAME} left near {o.x}, {o.z}: nobody slew it."
    if o.state == "off":
        return f"Act {o.act}: {NAME} was called off (the switch) before it rose near {o.x}, {o.z}."
    if o.state == "waiting":
        return f"Act {o.act}: {NAME} rises soon near {o.x}, {o.z}."
    if o.state == "fell":
        return f"Act {o.act}: {NAME} fell near {o.x}, {o.z} with nobody to claim it."
    return f"Act {o.act}: {NAME} is up near {o.x}, {o.z} ({o.health} health)."


# ---------------------------------------------------------------- the data pack


LAUNCHED_CHECK = f"execute unless score {LAUNCHED} matches 1"
OVERWORLD = f"execute in {saved_world.OVERWORLD}"


def red(msg: str) -> dict:
    return {"text": msg, "color": "red"}


def gold(msg: str) -> dict:
    return {"text": msg, "color": "gold"}


def summon_nbt() -> str:
    gear = ",".join(f'{slot}:{{id:"{item}",count:1}}' for slot, item in GEAR.items())
    drops = ",".join(f"{slot}:0.0f" for slot in GEAR)
    name = text({"text": NAME, "color": "dark_red", "bold": True})
    return (f'{{Tags:["{TAG}","bs.new"],PersistenceRequired:1b,CanPickUpLoot:0b,CustomNameVisible:1b,'
            f"CustomName:{name},equipment:{{{gear}}},drop_chances:{{{drops}}}}}")


def kill_advancement() -> dict:
    """Fires as a player who killed the boss (26.x shapes, as omens'): the victim carries its act in bs.id."""
    boss = {"type": "minecraft:entity_scores", "entity": "this", "scores": {ID: {"min": 1}}}
    return {"criteria": {"kill": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": boss}}},
            "requirements": [["kill"]], "rewards": {"function": f"{NS}:boss/slain"}}


def where(x: str = "$(x)", z: str = "$(z)") -> dict:
    return {"text": f"{x}, {z}", "color": "yellow"}


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP border boss: rises on each Season II border act (generated by tools/boss.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:boss/load")
    f[f"data/{NS}/advancement/boss/slain.json"] = json.dumps(kill_advancement(), indent=2)

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/boss.py. Scores and storage are kept across restarts; the switch starts off.",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard objectives add {ID} dummy",
        f"scoreboard players add #on {OBJ} 0",
        f"scoreboard players add #act {OBJ} 0",
        f"scoreboard players add #state {OBJ} 0",
        f"bossbar add {BAR} " + text({"text": NAME, "color": "dark_red"}),
        f"bossbar set {BAR} color red",
        f"bossbar set {BAR} style notched_10",
        f"schedule function {NS}:boss/second 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:boss/second 20t replace",
        "# A boss from one that ended (it was in an unloaded chunk then) goes as soon as it is seen.",
        f"execute unless score #state {OBJ} matches 2 as @e[type={MOB},tag={TAG}] run function {NS}:boss/vanish",
        f"execute if score #state {OBJ} matches 1 run function {NS}:boss/waiting",
        f"execute if score #state {OBJ} matches 2 run function {NS}:boss/up",
    )

    # ------------------------------------------------ the act: announce, keep the chunk, wait for the border
    f[f"{FN}/act.mcfunction"] = lines(
        "# Macro {act, x, z, delay}: sent by the border timer (tools/border.py) after it records border act N, or",
        f"# by staff. Each act is taken once (#act {OBJ}), so sending it again never makes a second boss.",
        f"execute unless score #on {OBJ} matches 1 run return 10",
        f"execute unless score {SEASON} matches 2.. run return 11",
        f"{LAUNCHED_CHECK} run return 12",
        f"execute if score {LOCKED} {STATE} matches 1 run return 13",
        f"$execute if score #act {OBJ} matches $(act).. run return 14",
        f"execute if score #state {OBJ} matches 1.. run return 15",
        f"$scoreboard players set #act {OBJ} $(act)",
        f"$data modify storage {STORE} at set value {{act:$(act),x:$(x),z:$(z),hp:0}}",
        f"$data modify storage {STORE} last set value {{x:$(x),z:$(z)}}",
        f"$data modify storage {STORE} acts.a$(act) set value {{state:\"waiting\",x:$(x),z:$(z),hp:0}}",
        f"$scoreboard players set #wait {OBJ} $(delay)",
        f"scoreboard players set #state {OBJ} 1",
        "# The spot's chunk stays loaded until the boss ends, so it can rise there and leave on time.",
        f"${OVERWORLD} run forceload add $(x) $(z)",
        "$tellraw @a " + text("", {"text": "Something stirs past the old edge. ", "color": "dark_red", "bold": True},
                              gold(f"When the border has grown, {NAME} rises near "), where(),
                              gold(". The first to slay it takes a Server First for their faction. A staff event: "
                                   f"within {EVENT_RADIUS} blocks of it anyone can fight anyone (rule 41).")),
        "return 1",
    )
    f[f"{FN}/waiting.mcfunction"] = lines(
        f"scoreboard players remove #wait {OBJ} 1",
        f"execute if score #wait {OBJ} matches 1.. run return 0",
        f"function {NS}:boss/rise with storage {STORE} at",
    )
    f[f"{FN}/rise.mcfunction"] = lines(
        "# Macro at {act, x, z, hp}: on the surface at the spot (the highest block that stops movement).",
        f"$execute in {saved_world.OVERWORLD} unless loaded $(x) 0 $(z) run return run "
        f"scoreboard players set #wait {OBJ} 1",
        f"${OVERWORLD} positioned $(x) 0 $(z) align xz positioned ~0.5 ~ ~0.5 positioned over "
        f"motion_blocking_no_leaves run function {NS}:boss/summon",
    )
    health = [
        f"execute store result score #hp {OBJ} if entity @a[gamemode=survival]",
        f"scoreboard players set #k {OBJ} {PER_PLAYER}",
        f"scoreboard players operation #hp {OBJ} *= #k {OBJ}",
        f"scoreboard players add #hp {OBJ} {BASE_HEALTH}",
        f"execute if score #hp {OBJ} matches ..{MIN_HEALTH - 1} run scoreboard players set #hp {OBJ} {MIN_HEALTH}",
        f"execute if score #hp {OBJ} matches {MAX_HEALTH + 1}.. run scoreboard players set #hp {OBJ} {MAX_HEALTH}",
        f"execute store result storage {STORE} at.hp int 1 run scoreboard players get #hp {OBJ}",
    ]
    f[f"{FN}/summon.mcfunction"] = lines(
        f"# Health: {BASE_HEALTH} + {PER_PLAYER} for each survival player online, from {MIN_HEALTH} to {MAX_HEALTH}.",
        *health,
        f"summon {MOB} ~ ~ ~ {summon_nbt()}",
        f"execute as @e[type={MOB},tag=bs.new] run function {NS}:boss/setup",
        f"scoreboard players set #left {OBJ} {LIFE_SECONDS}",
        f"scoreboard players set #state {OBJ} 2",
        f"execute store result bossbar {BAR} max run scoreboard players get #hp {OBJ}",
        f"execute store result bossbar {BAR} value run scoreboard players get #hp {OBJ}",
        f"bossbar set {BAR} visible true",
        f"function {NS}:boss/risen with storage {STORE} at",
        "playsound minecraft:entity.wither.spawn master @a ~ ~ ~ 1000 0.6",
    )
    f[f"{FN}/setup.mcfunction"] = lines(
        "# As the new boss: its act (the kill advancement reads it), its attributes and its health.",
        "tag @s remove bs.new",
        f"scoreboard players operation @s {ID} = #act {OBJ}",
        *(f"attribute @s {a} base set {v}" for a, v in ATTRIBUTES.items()),
        "effect give @s minecraft:fire_resistance infinite 0 true",
        f"function {NS}:boss/health with storage {STORE} at",
    )
    f[f"{FN}/health.mcfunction"] = lines(
        "$attribute @s minecraft:max_health base set $(hp)",
        "$data modify entity @s Health set value $(hp)f",
    )
    f[f"{FN}/risen.mcfunction"] = lines(
        "# Macro at {act, x, z, hp}: the record (news, recap, tools/boss.py status) and the announcement.",
        f"$data modify storage {STORE} acts.a$(act) set value {{state:\"risen\",x:$(x),z:$(z),hp:$(hp)}}",
        f"$execute store result storage {STORE} acts.a$(act).week int 1 run scoreboard players get #week rc.week",
        "$tellraw @a " + text("", {"text": f"{NAME} has risen ", "color": "dark_red", "bold": True},
                              gold("near "), where(), gold(" in the Overworld, with "),
                              {"text": "$(hp)", "color": "red"}, gold(f" health. It leaves in {LIFE_SECONDS // 60} "
                                                                     "minutes if nobody slays it. A staff event "
                                                                     f"until then: within {EVENT_RADIUS} blocks of "
                                                                     "it anyone can fight anyone (rule 41).")),
    )

    # ------------------------------------------------ while it is up
    f[f"{FN}/up.mcfunction"] = lines(
        f"execute store result score #seen {OBJ} if entity @e[type={MOB},tag={TAG}]",
        f"execute if score #seen {OBJ} matches 1.. as @e[type={MOB},tag={TAG},limit=1] at @s run function "
        f"{NS}:boss/track",
        "# Not found: in a chunk nobody has loaded (it waits), or dead without a player's kill.",
        f"execute if score #seen {OBJ} matches 0 run function {NS}:boss/missing with storage {STORE} last",
        f"execute unless score #state {OBJ} matches 2 run return 0",
        f"scoreboard players remove #left {OBJ} 1",
        f"execute if score #left {OBJ} matches {WARN_LEFT} run tellraw @a " + text(
            {"text": f"{NAME} leaves in {WARN_LEFT // 60} minutes.", "color": "gold"}),
        f"execute if score #left {OBJ} matches ..0 run function {NS}:boss/leave",
    )
    f[f"{FN}/track.mcfunction"] = lines(
        "# As the boss, at it: its health on the bar, for the players near it, and where it is.",
        f"execute store result bossbar {BAR} value run data get entity @s Health",
        f"bossbar set {BAR} players @a[distance=..{BAR_RANGE}]",
        f"execute store result storage {STORE} last.x int 1 run data get entity @s Pos[0]",
        f"execute store result storage {STORE} last.z int 1 run data get entity @s Pos[2]",
    )
    f[f"{FN}/missing.mcfunction"] = lines(
        "# Macro last {x, z}: where it was last seen is loaded and it isn't there: it died (lava, the void...).",
        f"${OVERWORLD} if loaded $(x) 0 $(z) run function {NS}:boss/fell",
    )
    f[f"{FN}/slain.mcfunction"] = lines(
        "# The kill advancement's reward, as the player who landed the killing blow.",
        f"advancement revoke @s only {NS}:boss/slain",
        f"execute unless score #state {OBJ} matches 2 run return 0",
        f"function {NS}:firsts/name",
        f"data modify storage {STORE} at.name set from storage {NS}:firsts name",
        f"scoreboard players set #f {OBJ} 0",
        f"execute if score @s st.faction matches 1.. run scoreboard players operation #f {OBJ} = @s st.faction",
        f"execute store result storage {STORE} at.faction int 1 run scoreboard players get #f {OBJ}",
        f"function {NS}:boss/slain_record with storage {STORE} at",
        f"execute if score #f {OBJ} matches 1.. run function {NS}:boss/slain_faction with storage {STORE} at",
        f"execute if score #f {OBJ} matches 0 run tellraw @a " + text(
            "", {"selector": "@s", "color": "yellow"}, {"text": f" slew {NAME}!", "color": "gold", "bold": True}),
        "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 0.8",
        f"function {NS}:boss/end",
    )
    f[f"{FN}/slain_record.mcfunction"] = lines(
        "$data modify storage " + STORE + " acts.a$(act) merge value {state:\"slain\",faction:$(faction)}",
        f"$data modify storage {STORE} acts.a$(act).name set from storage {STORE} at.name",
        f"$execute store result storage {STORE} acts.a$(act).week int 1 run scoreboard players get #week rc.week",
    )
    f[f"{FN}/slain_faction.mcfunction"] = lines(
        "$tellraw @a " + text("", {"selector": "@s", "color": "yellow"}, gold(" of "),
                              {"nbt": "names.f$(faction)", "storage": f"{NS}:factions", "interpret": True,
                               "color": "yellow"},
                              {"text": f" slew {NAME}! ", "color": "gold", "bold": True},
                              gold("Their banner goes in the Hall of Banners.")),
    )
    f[f"{FN}/fell.mcfunction"] = lines(
        f"function {NS}:boss/record {{state:\"fell\"}}",
        "tellraw @a " + text(gold(f"{NAME} fell, with nobody to claim it.")),
        f"function {NS}:boss/end",
    )
    f[f"{FN}/leave.mcfunction"] = lines(
        f"function {NS}:boss/record {{state:\"left\"}}",
        f"execute as @e[type={MOB},tag={TAG}] at @s run particle minecraft:large_smoke ~ ~2 ~ 1 2 1 0.05 200 force",
        f"execute as @e[type={MOB},tag={TAG}] run function {NS}:boss/vanish",
        "tellraw @a " + text(gold(f"{NAME} slips back past the edge. Nobody slew it this time.")),
        f"function {NS}:boss/end",
    )
    f[f"{FN}/record.mcfunction"] = lines(
        "# Macro {state}: the act's record ends this way.",
        f"$data modify storage {STORE} at.state set value \"$(state)\"",
        f"function {NS}:boss/record_at with storage {STORE} at",
    )
    f[f"{FN}/record_at.mcfunction"] = lines(
        f"$data modify storage {STORE} acts.a$(act).state set value \"$(state)\"",
        f"$execute store result storage {STORE} acts.a$(act).week int 1 run scoreboard players get #week rc.week",
    )
    f[f"{FN}/vanish.mcfunction"] = lines(
        "# As a boss: gone without a death (nothing drops, nobody gets a kill).",
        f"tag @s remove {TAG}",
        "execute at @s run tp @s ~ -200 ~",
        "kill @s",
    )
    f[f"{FN}/end.mcfunction"] = lines(
        f"scoreboard players set #state {OBJ} 0",
        f"bossbar set {BAR} visible false",
        f"bossbar set {BAR} players",
        f"function {NS}:boss/release with storage {STORE} at",
    )
    f[f"{FN}/release.mcfunction"] = lines(f"${OVERWORLD} run forceload remove $(x) $(z)")

    # ------------------------------------------------ staff
    f[f"{FN}/on.mcfunction"] = lines(
        "# Staff: the switch (docs/SEASONS.md, \"Switches\"). From Season II only.",
        f"execute unless score {SEASON} matches 2.. run return run tellraw @s " + text(red(
            "The border boss is for Season II on: this world is Season I (#season rw.day).")),
        f"scoreboard players set #on {OBJ} 1",
        "tellraw @s " + text(gold("The border boss is on: the next border act raises one.")),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        "# Staff: no boss on the next act; one that is up or waiting leaves now.",
        f"scoreboard players set #on {OBJ} 0",
        f"execute if score #state {OBJ} matches 2 run function {NS}:boss/record {{state:\"left\"}}",
        f"execute if score #state {OBJ} matches 1 run function {NS}:boss/record {{state:\"off\"}}",
        f"execute as @e[type={MOB},tag={TAG}] run function {NS}:boss/vanish",
        f"execute if score #state {OBJ} matches 1.. run function {NS}:boss/end",
        "tellraw @s " + text(gold("The border boss is off.")),
    )
    f[f"{FN}/status.mcfunction"] = lines(
        "tellraw @s " + text("", gold("Border boss: switch "), {"score": {"name": "#on", "objective": OBJ}},
                             gold(", last act "), {"score": {"name": "#act", "objective": OBJ}},
                             gold(", state "), {"score": {"name": "#state", "objective": OBJ}},
                             gold(" (0 none, 1 waiting to rise, 2 up), seconds left "),
                             {"score": {"name": "#left", "objective": OBJ}}),
        "tellraw @s " + text("", gold("Records: "), {"nbt": "acts", "storage": STORE, "color": "white"}),
    )
    f[f"{FN}/reset.mcfunction"] = lines(
        "# Staff, test servers only: forget every act, so the next act raises a boss again.",
        f"function {NS}:boss/off",
        f"scoreboard players set #act {OBJ} 0",
        f"data remove storage {STORE} acts",
    )
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- the command line


def main(argv=None) -> int:
    import border  # border imports this module

    import diplomacy
    ap = argparse.ArgumentParser(description="The border boss: where it rises, and what became of it.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("spot", help="where each act's boss rises, around a border centred at --center")
    s.add_argument("--season", type=int, default=2)
    s.add_argument("--center", type=float, nargs=2, default=(0.0, 0.0), metavar=("X", "Z"))
    w = sub.add_parser("status", help="each act's boss in the saved world")
    w.add_argument("world", type=Path)
    args = ap.parse_args(argv)
    if args.command == "spot":
        for act in border.acts(args.season):
            x, z = spot(args.season, act.number, *args.center, act.size)
            print(f"act {act.number} ({act.size} wide): near {x}, {z}")
        return 0
    if not args.world.is_dir():
        print(f"no world folder at {args.world}")
        return 2
    found = outcomes(args.world)
    names = diplomacy.names(args.world) if found else {}
    for o in found:
        print(describe(o, names))
    if not found:
        print("No border boss has risen in this world.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
