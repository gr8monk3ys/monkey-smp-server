"""Builds the event tooling: the arena, the Anarchy and raid timers, official flags, event books and the Cup.

    python tools/events.py          regenerate the data pack from the tables below
    python tools/events.py --check  exit 1 if the committed pack differs from what this would write

It writes one generated folder (edit this file, not it):
  package/realms/datapacks/realms-events/

docs/SEASONS.md says what each event is and why its rules are what they are; docs/ADMIN.md lists the
commands staff type. Everything here is run by staff with `/function realms:events/...`, except the
arena, which players join and leave with `/trigger arena`.

Scores (all in the data pack's load function):
  ev.state     #arena / #raid / #anarchy: 0 off, otherwise the phase; #flags and #event are counters
  ev.timer     seconds left in the running phase of each timer
  ev.strength  a player's real Strength level while they are in the arena
  rw.events    events a player has turned up to (a retention score, like the wardrobe's rw.*)
  ev.cup       the Season Cup, one entry per faction
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from repo import REPO, Repo

MINECRAFT = "26.3"     # DATA_FORMAT and the tables below are this version's; tests fail when the manifest moves on
DATA_FORMAT = 121
NS = "realms"
DATAPACK = "realms-events"
FN = f"data/{NS}/function/events"
STORE = f"{NS}:events"   # the command storage that holds the arena's points and the flag being made

# The Strength SMP mod's scores (silvers_strength-smp-season-4). Its tick adds one attack_damage
# modifier per level but only removes them at level 0, so setting a lower level by command has to
# remove the higher modifiers too (`strength_sync`).
LEVEL = "Strength_SMP+Strength_Level"
WITHDRAW = "Withdraw_Strength"
STRENGTH_ITEM = '*[custom_data~{"Strength_SMP+Item":{}}]'
KIT_ITEM = "*[custom_data~{realms_kit:{}}]"
NOT_KIT_ITEM = "*[!custom_data~{realms_kit:{}}]"
ARENA_LEVEL = 3   # the level every player starts with
# The player-death-corpses mod (a data pack in a jar) turns keep_inventory on and, the tick after a death,
# moves the dead player's gear onto a mannequin tagged player_corpses.corpse. A timer text_display with the
# same tag rides it, and a click box (an interaction) does when right-click looting is on.
CORPSE = "tag=player_corpses.corpse"
CORPSE_CLICK = "type=minecraft:interaction,tag=player_corpses.interaction"

COLORS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan",
          "purple", "blue", "brown", "green", "red", "black"]

# Enchantment books: every 26.3 enchantment at its vanilla maximum, except what the rules ban (B2 enchanted
# maces, B9 Fire Aspect and Flame) and the curses, which are no prize.
MAX_LEVEL = {
    "aqua_affinity": 1, "bane_of_arthropods": 5, "blast_protection": 4, "channeling": 1, "depth_strider": 3,
    "efficiency": 5, "feather_falling": 4, "fire_protection": 4, "fortune": 3, "frost_walker": 2, "impaling": 5,
    "infinity": 1, "knockback": 2, "looting": 3, "loyalty": 3, "luck_of_the_sea": 3, "lunge": 3, "lure": 3,
    "mending": 1, "multishot": 1, "piercing": 4, "power": 5, "projectile_protection": 4, "protection": 4,
    "punch": 2, "quick_charge": 3, "respiration": 3, "riptide": 3, "sharpness": 5, "silk_touch": 1, "smite": 5,
    "soul_speed": 3, "sweeping_edge": 3, "swift_sneak": 3, "thorns": 3, "unbreaking": 3,
}
NO_BOOK = {"fire_aspect", "flame", "breach", "density", "wind_burst", "binding_curse", "vanishing_curse"}

# Arena kits. Everyone gets the same unenchanted iron armor and food; nothing the bans cover (no totems,
# pearls, crystals, enchanted golden apples, enchantments or tipped arrows).
ARMOR = {"armor.head": "iron_helmet", "armor.chest": "iron_chestplate", "armor.legs": "iron_leggings",
         "armor.feet": "iron_boots"}
FOOD = [("cooked_beef", 8), ("golden_apple", 2)]
KITS = {
    "sword": [("iron_sword", 1), ("shield", 1)],
    "archer": [("bow", 1), ("crossbow", 1), ("arrow", 48), ("stone_sword", 1)],
    "axe": [("iron_axe", 1), ("shield", 1)],
    "spear": [("iron_spear", 1), ("shield", 1)],
    "mace": [("mace", 1), ("wind_charge", 8), ("stone_sword", 1)],
}
BANNED = {"totem_of_undying", "ender_pearl", "end_crystal", "enchanted_golden_apple", "tipped_arrow",
          "respawn_anchor", "tnt_minecart"}

# Anarchy's banned items: what staff clear from everyone online when the ceasefire ends (SEASONS.md).
CONTRABAND = ["totem_of_undying", "end_crystal", "enchanted_golden_apple"]

# Timers: each phase is (label, seconds, bossbar color, announcement). The last phase's end runs <name>/over.
TIMERS = {
    "anarchy": [
        ("Anarchy", 90 * 60, "red",
         "Anarchy for 90 minutes: the combat rules and gameplay bans are off. Griefing, cheating and "
         "conduct rules still apply."),
        ("Ceasefire", 10 * 60, "green",
         "Anarchy is over. 10-minute ceasefire: no fighting. Take down your traps and get rid of totems, "
         "end crystals and enchanted golden apples."),
    ],
    "raid": [
        ("Faction Raid", 120 * 60, "yellow",
         "The Faction Raid is on for 2 hours. Flags travel in your inventory only; every rule and ban "
         "applies."),
    ],
}
WARNINGS = (600, 300, 60)   # seconds left in the first phase when everyone is warned


def text(*parts) -> str:
    """A text component as compact JSON: one part as itself, several as a list."""
    value = parts[0] if len(parts) == 1 else list(parts)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def say(*parts) -> str:
    return "tellraw @s " + text(*parts)


def refuse(msg: str) -> str:
    return "return run " + say({"text": msg, "color": "red"})


def lines(*items) -> str:
    return "\n".join(items) + "\n"


def item(name: str) -> str:
    return f"minecraft:{name}"


def kit_item(name: str) -> str:
    """A kit item, marked so it is cleared wherever it turns up outside the arena."""
    return f"minecraft:{name}[custom_data={{realms_kit:{{}}}}]"


def at_point(prefix: str) -> str:
    """Macro: the overworld position of an arena point stored as <prefix>x/y/z."""
    return f"in minecraft:overworld positioned $({prefix}x) $({prefix}y) $({prefix}z)"


# ---------------------------------------------------------------- the data pack


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = json.dumps({"pack": {
        "description": "Monkey SMP events: arena, Anarchy, raids, flags, the Cup (generated by tools/events.py)",
        "min_format": DATA_FORMAT, "max_format": DATA_FORMAT}}, indent=2)
    f["data/minecraft/tags/function/load.json"] = json.dumps({"values": [f"{NS}:events/load"]}, indent=2)
    f["data/minecraft/tags/function/tick.json"] = json.dumps({"values": [f"{NS}:events/tick"]}, indent=2)

    objectives = ["ev.state dummy", "ev.timer dummy", "ev.strength dummy", "ev.deaths deathCount",
                  "ev.left minecraft.custom:minecraft.leave_game", "ev.seen dummy", "rw.events dummy",
                  "arena trigger", 'ev.cup dummy {"text":"Season Cup","color":"gold"}']
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/events.py. Scores and storage are kept across restarts.",
        *(f"scoreboard objectives add {o}" for o in objectives),
        "scoreboard players set #60 ev.timer 60",
        f"execute unless data storage {STORE} arena.size run data modify storage {STORE} arena.size set value 48",
        f"schedule function {NS}:events/second 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        f"execute if score #arena ev.state matches 1 run function {NS}:events/arena/tick with storage {STORE} arena",
        f"execute as @a[scores={{arena=1..}}] run function {NS}:events/arena/use",
        "# Anyone still marked as in the arena once it has closed (they were dead or offline when it did).",
        f"execute unless score #arena ev.state matches 1 as @e[type=player,tag=ev.arena] run function "
        f"{NS}:events/arena/leave with storage {STORE} arena",
        f"execute as @e[type=player,scores={{ev.left=1..}}] run function {NS}:events/rejoined",
        "# Kit gear smuggled out (an ender chest, a chest boat, a hopper under the floor) is gone once picked up.",
        f"clear @a[tag=!ev.arena] {KIT_ITEM}",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:events/second 20t replace",
        "execute if score #arena ev.state matches 1 run scoreboard players enable @a arena",
        *(f"execute if score #{name} ev.state matches 1.. run function {NS}:events/{name}/second" for name in TIMERS),
    )
    f[f"{FN}/rejoined.mcfunction"] = lines(
        "# A player who logged out came back.",
        "scoreboard players reset @s ev.left",
        "execute if entity @s[tag=ev.arena] run " + say(
            {"text": "You logged out in the arena, so you're out: your Strength is back.", "color": "yellow"}),
        f"execute if entity @s[tag=ev.arena] run function {NS}:events/arena/leave with storage {STORE} arena",
        "# A flag carried out of a raid by logging out goes back to its faction.",
        "execute unless score #raid ev.state matches 1.. run return 0",
        "execute store result score #taken ev.state run clear @s *[custom_data~{realms_flag:{}}]",
        "execute if score #taken ev.state matches 1.. run tellraw @a " + text(
            {"selector": "@s", "color": "yellow"},
            {"text": " logged out with a flag. It goes back to its faction; staff will return it.",
             "color": "yellow"}),
    )
    f.update(arena_files())
    f.update(timer_files())
    f.update(flag_files())
    f.update(book_files())
    f.update(cup_files())
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def arena_files() -> dict[str, str]:
    f: dict[str, str] = {}
    fn = f"{FN}/arena"
    arena = f"with storage {STORE} arena"
    f[f"data/{NS}/tags/entity_type/holds_items.json"] = json.dumps({"values": [
        f"minecraft:{e}" for e in ("chest_minecart", "hopper_minecart", "bamboo_chest_raft", *(
            f"{wood}_chest_boat" for wood in ("oak", "spruce", "birch", "jungle", "acacia", "cherry", "dark_oak",
                                              "pale_oak", "mangrove", "poplar")),
            "donkey", "mule", "llama", "trader_llama")]}, indent=2)
    f[f"{fn}/strength_sync.mcfunction"] = lines(
        "# Removes the Strength mod's damage modifiers above the player's level; the mod adds the rest.",
        *(f"attribute @s[scores={{{LEVEL}=..{n - 1}}}] minecraft:attack_damage modifier remove "
          f"strength_smp:buff-level_{n}" for n in range(2, 6)),
    )
    for point, prefix, what in (("lobby", "l", "the arena's entrance: players join here and leave to here"),
                                ("pit", "p", "the waiting room inside: players arrive and respawn here")):
        f[f"{fn}/set_{point}.mcfunction"] = lines(
            f"# Run standing at {what}.",
            "execute unless dimension minecraft:overworld run " + refuse("The arena has to be in the overworld."),
            *(f"execute store result storage {STORE} arena.{prefix}{axis} int 1 run data get entity @s Pos[{i}]"
              for i, axis in enumerate("xyz")),
            say({"text": f"Arena {point} set here.", "color": "green"}),
        )
    f[f"{fn}/set_size.mcfunction"] = lines(
        "# Macro {size:N}: the arena's radius around the pit; keep it inside the walls. Items there, and",
        "# anything that holds items (minecarts, chest boats, donkeys, llamas), are removed every tick, and a",
        "# player in the arena who ends up farther away (a teleport) is taken out.",
        f"$data modify storage {STORE} arena.size set value $(size)",
        say({"text": "Arena size set.", "color": "green"}),
    )
    f[f"{fn}/open.mcfunction"] = lines(
        f"execute unless data storage {STORE} arena.lx run " + refuse(
            f"Set the entrance first: /function {NS}:events/arena/set_lobby"),
        f"execute unless data storage {STORE} arena.px run " + refuse(
            f"Set the waiting room first: /function {NS}:events/arena/set_pit"),
        "scoreboard players set #arena ev.state 1",
        "scoreboard players enable @a arena",
        "tellraw @a " + text(
            {"text": "Arena Glory is open. ", "color": "gold"},
            {"text": "Come to the arena entrance with an empty inventory and ", "color": "gray"},
            {"text": "[join]", "color": "green",
             "click_event": {"action": "run_command", "command": "/trigger arena set 1"},
             "hover_event": {"action": "show_text", "value": "Your Strength is set to +3 inside; your gear stays "
                                                              "safe because you bring none."}},
            {"text": ". Your real Strength comes back when you leave.", "color": "gray"}),
    )
    f[f"{fn}/close.mcfunction"] = lines(
        "scoreboard players set #arena ev.state 0",
        f"execute as @e[type=player,tag=ev.arena] run function {NS}:events/arena/leave {arena}",
        f"function {NS}:events/arena/round {arena}",
        "tellraw @a " + text({"text": "Arena Glory is closed. Thanks for fighting.", "color": "gold"}),
    )
    f[f"{fn}/round.mcfunction"] = lines(
        "# Between rounds: clear the floor (items go every tick anyway; this takes arrows and tridents too).",
        *(f"$execute {at_point('p')} run kill @e[{what},distance=..$(size)]" for what in (CORPSE, CORPSE_CLICK)),
        f"$execute {at_point('p')} run kill @e[type=#minecraft:arrows,distance=..$(size)]",
        f"$execute {at_point('p')} run kill @e[type=minecraft:trident,distance=..$(size)]",
        f"$execute {at_point('p')} run kill @e[type=minecraft:item,distance=..$(size)]",
    )
    f[f"{fn}/use.mcfunction"] = lines(
        "# /trigger arena: 1 joins, 2 leaves.",
        "execute if score @s arena matches 1 unless score #arena ev.state matches 1 run "
        + say({"text": "The arena is closed.", "color": "red"}),
        f"execute if score @s arena matches 1 if score #arena ev.state matches 1 run function "
        f"{NS}:events/arena/join {arena}",
        f"execute if score @s arena matches 2 if entity @s[tag=ev.arena] run function "
        f"{NS}:events/arena/leave {arena}",
        "scoreboard players set @s arena 0",
    )
    f[f"{fn}/join.mcfunction"] = lines(
        "execute if entity @s[tag=ev.arena] run " + refuse("You're already in. /trigger arena set 2 leaves."),
        "execute unless entity @s[gamemode=survival] run " + refuse("Only players in survival can join."),
        "$execute in minecraft:overworld unless entity @s[x=$(lx),y=$(ly),z=$(lz),distance=..8] run "
        + refuse("Come to the arena entrance to join."),
        *(f"execute if items entity @s {slots} * run " + refuse(
            "Empty your inventory, armor and offhand first: you fight with the round's kit, not your gear.")
          for slots in ("container.*", "armor.*", "weapon.offhand")),
        "# Leaving strips kit gear from the ender chest's slots, but not from inside a bundle kept there.",
        "execute if items entity @s enderchest.* #minecraft:bundles run " + refuse(
            "Take the bundles out of your ender chest first."),
        "tag @s add ev.arena",
        f"scoreboard players operation @s ev.strength = @s {LEVEL}",
        f"scoreboard players set @s {LEVEL} {ARENA_LEVEL}",
        f"function {NS}:events/arena/strength_sync",
        "scoreboard players set @s ev.deaths 0",
        "effect clear @s",
        "gamemode adventure @s",
        f"$execute {at_point('p')} run tp @s ~ ~ ~",
        f"function {NS}:events/attend",
        say({"text": f"You're in. Your Strength is +{ARENA_LEVEL} until you leave, and nothing you get here "
                     "leaves with you. ", "color": "green"},
            {"text": "[leave]", "color": "aqua",
             "click_event": {"action": "run_command", "command": "/trigger arena set 2"}}),
    )
    f[f"{fn}/leave.mcfunction"] = lines(
        "# Out of the arena: nothing comes with you, and your real Strength comes back.",
        "tag @s remove ev.arena",
        "tag @s remove ev.away",
        "clear @s",
        "item replace entity @s player.cursor with minecraft:air",
        *(f"item replace entity @s player.crafting.{i} with minecraft:air" for i in range(4)),
        "# Kit gear stashed in the ender chest stays here. So does any bundle: there was none at the join.",
        *(f"execute if items entity @s enderchest.{i} {what} run item replace entity @s enderchest.{i} "
          "with minecraft:air" for i in range(27) for what in (KIT_ITEM, "#minecraft:bundles")),
        "effect clear @s",
        f"scoreboard players operation @s {LEVEL} = @s ev.strength",
        "scoreboard players reset @s ev.strength",
        f"function {NS}:events/arena/strength_sync",
        "gamemode survival @s",
        f"$execute {at_point('l')} run tp @s ~ ~ ~",
        say({"text": "You left the arena. Your Strength is back to +", "color": "gray"},
            {"score": {"name": "@s", "objective": LEVEL}, "color": "white"}, {"text": ".", "color": "gray"}),
    )
    f[f"{fn}/tick.mcfunction"] = lines(
        "# Every tick while the arena is open (macro: the arena's points).",
        "# Strength stays at the arena level: kills gain none, deaths cost none, nothing can be withdrawn.",
        f"scoreboard players set @a[tag=ev.arena] {LEVEL} {ARENA_LEVEL}",
        f"scoreboard players reset @a[tag=ev.arena] {WITHDRAW}",
        f"execute as @a[tag=ev.arena] run function {NS}:events/arena/strength_sync",
        f"clear @a[tag=ev.arena] {STRENGTH_ITEM}",
        "# Players in the arena hold kit gear and nothing else (no bundle to hide gear in).",
        f"clear @a[tag=ev.arena] {NOT_KIT_ITEM}",
        "# Nothing dropped in the arena survives a tick, so nothing can be passed over the wall, and nothing",
        "# that holds items (a chest minecart, a chest boat, a donkey) can carry gear or a bundle out: killing",
        "# one drops its contents, which the next line removes. Kit gear stashed anywhere else is marked, and",
        "# cleared from whoever takes it out (tick.mcfunction).",
        f"$execute {at_point('p')} run kill @e[type=#{NS}:holds_items,distance=..$(size)]",
        "# A death leaves a corpse holding the kit (CORPSE in tools/events.py), which anyone could loot for a",
        "# second kit: it goes the same way, with its timer and click box, and what it drops goes next.",
        *(f"$execute {at_point('p')} run kill @e[{what},distance=..$(size)]" for what in (CORPSE, CORPSE_CLICK)),
        f"$execute {at_point('p')} run kill @e[type=minecraft:item,distance=..$(size)]",
        f"$execute {at_point('p')} run kill @e[type=minecraft:experience_orb,distance=..$(size)]",
        "# Died: back to the waiting room, still in the arena.",
        f"$execute as @e[type=player,tag=ev.arena,scores={{ev.deaths=1..}}] {at_point('p')} run tp @s ~ ~ ~",
        "scoreboard players set @e[type=player,tag=ev.arena,scores={ev.deaths=1..}] ev.deaths 0",
        "# Anyone in the arena who is somewhere else (a teleport, another dimension) is taken out.",
        "tag @a[tag=ev.arena] add ev.away",
        f"$execute {at_point('p')} run tag @a[tag=ev.arena,distance=..$(size)] remove ev.away",
        f"execute as @a[tag=ev.away] run function {NS}:events/arena/leave with storage {STORE} arena",
    )
    for kit, items in KITS.items():
        f[f"{fn}/kit/{kit}.mcfunction"] = lines(
            f"# Run as the players in the arena: execute as @a[tag=ev.arena] run function {NS}:events/arena/kit/{kit}",
            "execute unless entity @s[tag=ev.arena] run " + refuse("Kits are only for players in the arena."),
            "clear @s",
            "effect clear @s",
            "effect give @s minecraft:instant_health 1 10 true",
            "effect give @s minecraft:saturation 1 10 true",
            *(f"item replace entity @s {slot} with {kit_item(name)}" for slot, name in ARMOR.items()),
            *(f"give @s {kit_item(name)} {n}" for name, n in [*items, *FOOD]),
            say({"text": f"Kit: {kit}.", "color": "green"}),
        )
    return f


def timer_files() -> dict[str, str]:
    f: dict[str, str] = {}
    for name, phases in TIMERS.items():
        fn = f"{FN}/{name}"
        bar = f"{NS}:{name}"
        f[f"{fn}/start.mcfunction"] = lines(
            f"execute if score #{name} ev.state matches 1.. run " + refuse(
                f"It's already running. /function {NS}:events/{name}/stop ends it early."),
            f"bossbar add {bar} " + text(phases[0][0]),
            f"function {NS}:events/{name}/phase1",
        )
        for k, (label, seconds, color, announce) in enumerate(phases, 1):
            f[f"{fn}/phase{k}.mcfunction"] = lines(
                f"scoreboard players set #{name} ev.state {k}",
                f"scoreboard players set #{name} ev.timer {seconds}",
                f"bossbar set {bar} max {seconds}",
                f"bossbar set {bar} value {seconds}",
                f"bossbar set {bar} color {color}",
                f"bossbar set {bar} players @a",
                f"bossbar set {bar} visible true",
                f"bossbar set {bar} name " + text({"text": label, "color": color}),
                "title @a times 10 60 20",
                "title @a title " + text({"text": label, "color": color}),
                "tellraw @a " + text({"text": announce, "color": color}),
                "playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1",
            )
        last = len(phases)
        second = [f"scoreboard players remove #{name} ev.timer 1",
                  f"execute store result bossbar {bar} value run scoreboard players get #{name} ev.timer",
                  f"scoreboard players operation #{name}_min ev.timer = #{name} ev.timer",
                  f"scoreboard players add #{name}_min ev.timer 59",
                  f"scoreboard players operation #{name}_min ev.timer /= #60 ev.timer",
                  f"bossbar set {bar} players @a"]
        for k, (label, _, color, _) in enumerate(phases, 1):
            second.append(f"execute if score #{name} ev.state matches {k} run bossbar set {bar} name " + text(
                {"text": f"{label}: ", "color": color},
                {"score": {"name": f"#{name}_min", "objective": "ev.timer"}, "color": "white"},
                {"text": " min left", "color": color}))
        for s in WARNINGS:
            what = f"{s // 60} minute{'s' if s > 60 else ''}"
            second.append(f"execute if score #{name} ev.state matches 1 if score #{name} ev.timer matches {s} "
                          "run tellraw @a " + text({"text": f"{phases[0][0]}: {what} left.",
                                                    "color": phases[0][2]}))
        for k in range(1, last + 1):
            then = f"phase{k + 1}" if k < last else "over"
            second.append(f"execute if score #{name} ev.state matches {k} if score #{name} ev.timer matches ..0 "
                          f"run return run function {NS}:events/{name}/{then}")
        f[f"{fn}/second.mcfunction"] = lines(*second)
        f[f"{fn}/stop.mcfunction"] = lines(
            f"# Ends {name} early, without what its end does.",
            f"scoreboard players set #{name} ev.state 0",
            f"scoreboard players set #{name} ev.timer 0",
            f"bossbar remove {bar}",
            "tellraw @a " + text({"text": f"Staff ended the {phases[0][0]} early.", "color": "gray"}),
        )
    f[f"{FN}/anarchy/over.mcfunction"] = lines(
        "# The ceasefire is over: normal rules again, and the banned items go.",
        "scoreboard players set #anarchy ev.state 0",
        "bossbar remove realms:anarchy",
        *(f"clear @a {item(c)}" for c in CONTRABAND),
        "tellraw @a " + text({"text": "The ceasefire is over and the normal rules are back. Totems, end crystals "
                                      "and enchanted golden apples were cleared; any found later fall under the "
                                      "bans.", "color": "green"}),
    )
    f[f"{FN}/raid/over.mcfunction"] = lines(
        "scoreboard players set #raid ev.state 0",
        "bossbar remove realms:raid",
        "title @a title " + text({"text": "Raid over", "color": "yellow"}),
        "tellraw @a " + text({"text": "The raid is over. Stop fighting: staff are counting the flags in every "
                                      "yard.", "color": "yellow"}),
    )
    return f


def flag_files() -> dict[str, str]:
    f: dict[str, str] = {}
    fn = f"{FN}/flag"
    f[f"{fn}/make.mcfunction"] = lines(
        "# Macro {id:\"red\",name:\"Red Monkeys\"}, run holding the faction's banner: makes it the official flag.",
        "# Each flag gets the next number. A copy made by crafting has the same number, so two flags with one",
        "# number means one is a copy (B13).",
        "execute unless items entity @s weapon.mainhand #minecraft:banners run " + refuse(
            "Hold the faction's banner in your main hand."),
        f'$data modify storage {STORE} flag set value {{id:"$(id)",name:"$(name)"}}',
        f"execute store result storage {STORE} flag.n int 1 run scoreboard players add #flags ev.state 1",
        f"function {NS}:events/flag/stamp with storage {STORE} flag",
    )
    stamp = [
        {"type": "minecraft:set_count", "count": 1},
        {"type": "minecraft:set_components", "components": {
            "minecraft:custom_data": {"realms_flag": {"id": "$(id)", "n": 0}},
            "minecraft:custom_name": {"text": "$(name) flag", "color": "gold", "italic": False},
            "minecraft:lore": [{"text": "Official flag no. $(n)", "color": "gray", "italic": False},
                               {"text": "Monkey SMP Faction Raid", "color": "dark_gray", "italic": False}],
            "minecraft:enchantment_glint_override": True}},
    ]
    modifier = json.dumps(stamp, separators=(",", ":")).replace('"n":0', '"n":$(n)')
    f[f"{fn}/stamp.mcfunction"] = lines(
        "# Macro {id, name, n} from flag/make. One banner only: extra banners in the stack are used up.",
        f"$item modify entity @s weapon.mainhand {modifier}",
        "$" + say({"text": "Official flag no. $(n) for $(name).", "color": "green"}),
    )
    # A banner keeps its components when placed, but vanilla only copies a few of them back when it is
    # broken. These copy the flag's tag and lore too, so a captured flag is still official.
    for color in COLORS:
        banner = f"minecraft:{color}_banner"
        f[f"data/minecraft/loot_table/blocks/{color}_banner.json"] = json.dumps({
            "type": "minecraft:block",
            "pools": [{
                "condition": {"type": "minecraft:survives_explosion"},
                "entries": [{
                    "type": "minecraft:item",
                    "modifier": {"type": "minecraft:copy_components", "source": "block_entity", "include": [
                        "minecraft:custom_name", "minecraft:item_name", "minecraft:tooltip_display",
                        "minecraft:banner_patterns", "minecraft:rarity",
                        "minecraft:custom_data", "minecraft:lore", "minecraft:enchantment_glint_override"]},
                    "name": banner}],
                "rolls": 1}],
            "random_sequence": f"minecraft:blocks/{color}_banner"}, indent=2)
    return f


def book_files() -> dict[str, str]:
    f: dict[str, str] = {}
    for ench, level in MAX_LEVEL.items():
        components = (f'stored_enchantments={{"minecraft:{ench}":{level}}},'
                      'lore=[{text:"Monkey SMP event reward, Season $(season)",color:"gold",italic:false}],'
                      'custom_data={realms_event_book:{season:"$(season)"}}')
        f[f"{FN}/book/{ench}.mcfunction"] = lines(
            f"# Macro {{season:\"I\"}}, run as the winner: one event book (B18), {ench} {level}.",
            f"$give @s minecraft:enchanted_book[{components}]",
        )
    return f


def cup_files() -> dict[str, str]:
    f: dict[str, str] = {}
    fn = f"{FN}/cup"
    f[f"{fn}/faction.mcfunction"] = lines(
        "# Macro {id:\"red\",name:\"Red Monkeys\"}: puts a faction on the Cup with 0 points.",
        "$scoreboard players add $(id) ev.cup 0",
        '$scoreboard players display name $(id) ev.cup "$(name)"',
    )
    f[f"{fn}/add.mcfunction"] = lines(
        "# Macro {id:\"red\",points:30,why:\"Build Battle, 1st\"}.",
        "$scoreboard players add $(id) ev.cup $(points)",
        "$tellraw @a " + text({"text": "Season Cup: ", "color": "gold"},
                              {"text": "+$(points) to $(id)", "color": "white"},
                              {"text": " ($(why)). Now ", "color": "gray"},
                              {"score": {"name": "$(id)", "objective": "ev.cup"}, "color": "white"},
                              {"text": ".", "color": "gray"}),
    )
    f[f"{fn}/show.mcfunction"] = lines("scoreboard objectives setdisplay sidebar ev.cup")
    f[f"{fn}/hide.mcfunction"] = lines("scoreboard objectives setdisplay sidebar")
    f[f"{FN}/begin.mcfunction"] = lines(
        "# Macro {name:\"Faction Raid\"}: starts a new event, so everyone can be counted once for it.",
        "scoreboard players add #event ev.state 1",
        "$tellraw @a " + text({"text": "Event: $(name)", "color": "gold"}),
    )
    f[f"{FN}/attend.mcfunction"] = lines(
        "# Run as a player who turned up (the arena does it on join). Counts once per event.",
        "execute if score @s ev.seen = #event ev.state run return 0",
        "scoreboard players operation @s ev.seen = #event ev.state",
        "scoreboard players add @s rw.events 1",
    )
    return f


HELP = [
    ("arena/set_lobby", "stand at the entrance"), ("arena/set_pit", "stand in the waiting room"),
    ("arena/set_size {size:48}", "radius around the pit"), ("arena/open", ""), ("arena/round", "clear the floor"),
    ("arena/kit/sword", "as @a[tag=ev.arena]"), ("arena/close", ""),
    ("anarchy/start", "90 min, then 10 min ceasefire"), ("raid/start", "2 hours"),
    ('flag/make {id:"red",name:"Red Monkeys"}', "hold the banner"),
    ('book/sharpness {season:"I"}', "as the winner"),
    ('cup/faction {id:"red",name:"Red Monkeys"}', ""), ('cup/add {id:"red",points:30,why:"Build Battle"}', ""),
    ("cup/show", ""), ('begin {name:"Faction Raid"}', ""), ("attend", "as each player who came"),
]


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box."]
    out.append(say({"text": "Event commands (docs/ADMIN.md):", "color": "gold"}))
    for cmd, note in HELP:
        path = cmd.split(" ")[0]
        assert f"{FN}/{path}.mcfunction" in files, path
        full = f"/function {NS}:events/{cmd}"
        out.append(say({"text": f" {cmd}", "color": "aqua",
                        "click_event": {"action": "suggest_command", "command": full}},
                       {"text": f"  {note}" if note else "", "color": "dark_gray"}))
    return lines(*out)


# ---------------------------------------------------------------- writing


def outputs(repo: Repo) -> dict[Path, bytes]:
    dp = repo.realms / "datapacks" / DATAPACK
    return {dp / k: v.encode() for k, v in datapack_files().items()}


def roots(repo: Repo) -> list[Path]:
    return [repo.realms / "datapacks" / DATAPACK]


def differences(repo: Repo) -> list[str]:
    want = outputs(repo)
    have = {p for r in roots(repo) if r.is_dir() for p in r.rglob("*") if p.is_file()}
    diff = [str(p.relative_to(repo.root)) for p, data in want.items() if not p.is_file() or p.read_bytes() != data]
    diff += [str(p.relative_to(repo.root)) + " (not generated)" for p in have - set(want)]
    return sorted(diff)


def write(repo: Repo) -> int:
    for r in roots(repo):
        shutil.rmtree(r, ignore_errors=True)
    for path, data in outputs(repo).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(outputs(repo))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Builds the events data pack.")
    ap.add_argument("--check", action="store_true", help="fail if the committed pack is out of date")
    args = ap.parse_args(argv)
    if args.check:
        diff = differences(REPO)
        if diff:
            print("events pack is out of date (run python tools/events.py):\n  " + "\n  ".join(diff))
            return 1
        print("events pack is up to date")
        return 0
    print(f"wrote {write(REPO)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
