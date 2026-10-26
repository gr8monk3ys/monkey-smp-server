"""Builds the data packs that make the server enforce the Season I rules players shouldn't have to police.

    python tools/rules.py          regenerate both packs
    python tools/rules.py --check  exit 1 if the committed packs differ from what this would write

It writes two folders, both generated (edit this file, not them). Rule numbers are docs/RULES.md's.

  package/realms/datapacks/realms-rules/
      Rule 25: a 2500 x 2500 world border centred on spawn (and the Nether's at 1:8), set once.
      Rule 23: the launch hour. `function realms:rules/launch` closes PvP and the Nether for an hour,
               then opens both; the End stays closed until `function realms:rules/open_end`.
      Rule 26: a first join gets 48 hours of PvP grace: other players can't hurt them. Attacking a player
               ends it, and so does `/trigger end_grace`. Nobody gets it during the launch hour.
      Ban B9:  Fire Aspect and Flame are disabled. They're out of the enchanting table, loot and trades,
               and any copy that still turns up (a mod's chest or a mob's gear) does nothing and can't be
               put on an item.
      Onboarding: a welcome notice a few seconds after the first join (its one button: the factions that
               are recruiting, on the Discord), and a Monkey SMP button in the pause menu with the
               Discord, map, rules and store links.

  package/realms/datapacks/realms-no-netherite-armor/
      Rule 24: no Netherite armor. The smithing table won't make it, and armor found in loot is taken off
               (it drops at the player's feet, nothing is lost). Netherite tools and weapons are fine.
      The owners lift the rule with `datapack disable "file/realms-no-netherite-armor"`; the world
      remembers that across restarts and updates.

The installer copies both into the world on every install (Install-PackageDatapacks).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from repo import REPO, Repo

MINECRAFT = "26.3"     # the formats and vanilla lists below are this version's; tests fail when it moves on
DATA_FORMAT = 121
NS = "realms"
RULES_PACK = "realms-rules"
NETHERITE_PACK = "realms-no-netherite-armor"

BORDER = 2500          # rule 25: the border's full width in blocks, centred on spawn
LAUNCH_SECONDS = 3600  # rule 23: how long PvP and the Nether stay closed after launch
OBJECTIVE = "realms.rules"

# Rule 26. Grace is a custom enchantment whose only effect is immunity to damage a player causes (melee,
# arrows, their TNT), on an item in the player's body slot: players have no screen for that slot, and
# Minecraft checks every slot's enchantments for immunity. The item comes back after a death until the
# grace runs out.
GRACE_HOURS = 48
GRACE_TICKS = GRACE_HOURS * 72_000  # game time, which stops while the server is empty
GRACE = "realms.grace"               # each player's grace end, in game time
END_GRACE = "end_grace"              # the trigger players end their own grace with
WELCOME = "realms.welcome"           # seconds until the welcome shows (a first join is still loading)
WELCOME_DELAY = 3
JOINED = "realms.joined"             # tag: seen before, so no welcome and no grace
GRACE_ITEM = "*[custom_data~{realms_grace:{}}]"
# A player's body slot only takes an item that is equippable there.
GRACE_STACK = ('minecraft:paper[custom_data={realms_grace:{}},enchantments={"realms:pvp_grace":1},'
               'equippable={slot:"body"},item_name="PvP grace"]')
ARENA = "ev.arena"  # tools/events.py tags the players in the event arena: an event, so no grace there
# The player-death-corpses mod copies a dead player's equipment, body slot included, onto this mannequin.
CORPSE = "type=minecraft:mannequin,tag=player_corpses.corpse"

# The welcome and the pause menu's links. The Discord invite is site/config.js's.
DISCORD = "https://discord.gg/C25hy9Ca9W"
SITE = "https://monkeysmp.lscaturchio.xyz"
MAP = "https://map.monkeysmp.lscaturchio.xyz"
LINKS = (("Discord", DISCORD, "Factions, events, tickets and the full rulebook"),
         ("Live map", MAP, "The world as it is, in your browser"),
         ("Rules", f"{SITE}/#rules", "The short rules on the website"),
         ("Store", f"{SITE}/#pricing", "The Server Pass and supporter tiers"))

BANNED_ENCHANTMENTS = ("minecraft:fire_aspect", "minecraft:flame")
# Vanilla 26.3's #minecraft:non_treasure. The enchanting table, random loot, villager trades and mob
# gear all draw from it, so the pack replaces it with this list minus the banned ones. No mod in the pack
# adds to it; one that does would lose its addition (see the RULES.md admin notes).
VANILLA_NON_TREASURE = (
    "protection", "fire_protection", "feather_falling", "blast_protection", "projectile_protection",
    "respiration", "aqua_affinity", "thorns", "depth_strider", "sharpness", "smite", "bane_of_arthropods",
    "knockback", "fire_aspect", "looting", "sweeping_edge", "efficiency", "silk_touch", "unbreaking", "fortune",
    "power", "punch", "flame", "infinity", "luck_of_the_sea", "lure", "loyalty", "impaling", "riptide",
    "channeling", "multishot", "quick_charge", "piercing", "density", "breach", "lunge",
)
# Vanilla's definitions with the effects taken out and nothing allowed to carry them.
DISABLED = {
    "fire_aspect": {"anvil_cost": 4, "max_cost": {"base": 60, "per_level_above_first": 20}, "max_level": 2,
                    "min_cost": {"base": 10, "per_level_above_first": 20}, "weight": 2},
    "flame": {"anvil_cost": 4, "max_cost": {"base": 50, "per_level_above_first": 0}, "max_level": 1,
              "min_cost": {"base": 20, "per_level_above_first": 0}, "weight": 2},
}

ARMOR_SLOTS = ("head", "chest", "legs", "feet")
NETHERITE_ARMOR = ("netherite_helmet", "netherite_chestplate", "netherite_leggings", "netherite_boots")
# 26.3 can't drop a vanilla recipe (other data refers to it, and the server won't start), so the upgrade is
# replaced by one that needs a barrier as its template: no survival player can ever fill it in.
NEVER_TEMPLATE = "minecraft:barrier"


def never(item: str) -> dict:
    return {"type": "minecraft:smithing_transform", "addition": "#minecraft:netherite_tool_materials",
            "base": "minecraft:" + item.replace("netherite_", "diamond_"), "result": {"id": f"minecraft:{item}"},
            "template": NEVER_TEMPLATE}


def text(*parts: object) -> str:
    return json.dumps(list(parts), separators=(",", ":"))


def js(obj) -> str:
    return json.dumps(obj, indent=2) + "\n"


def mcfunction(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def announce(message: str, color: str) -> str:
    return "tellraw @a " + text({"text": "[Monkey SMP] ", "color": "gold"}, {"text": message, "color": color})


def pack_meta(description: str) -> str:
    return js({"pack": {"description": f"{description} (generated by tools/rules.py)",
                        "min_format": DATA_FORMAT, "max_format": DATA_FORMAT}})


def rules_files() -> dict[str, str]:
    fn = f"data/{NS}/function/rules"
    f: dict[str, str] = {
        "pack.mcmeta": pack_meta("Monkey SMP Season I rules: border, launch hour, PvP grace, no Fire Aspect "
                                 "or Flame, welcome and links"),
        "data/minecraft/tags/function/load.json": js({"values": [f"{NS}:rules/load"]}),
    }
    f[f"{fn}/load.mcfunction"] = mcfunction(
        "# Generated by tools/rules.py. Runs on every start and /reload.",
        f"scoreboard objectives add {OBJECTIVE} dummy",
        f"scoreboard objectives add {GRACE} dummy",
        f"scoreboard objectives add {WELCOME} dummy",
        f"scoreboard objectives add {END_GRACE} trigger",
        "# Rule 25, once per world: after that the border is the admins' to grow.",
        f"execute unless score #border {OBJECTIVE} matches 1 run function {NS}:rules/border",
        f"schedule function {NS}:rules/second 20t replace",
    )
    f[f"{fn}/border.mcfunction"] = mcfunction(
        "# A function run by the server runs at the world spawn, so ~ ~ is spawn.",
        "execute in minecraft:overworld run worldborder center ~ ~",
        f"execute in minecraft:overworld run worldborder set {BORDER}",
        "# Since 26.3 each dimension has its own border (the Nether's no longer follows the overworld's), so",
        "# give the Nether the one it used to have: the same area at its 1:8 scale.",
        f"execute summon minecraft:marker run function {NS}:rules/nether_border",
        f"scoreboard players set #border {OBJECTIVE} 1",
    )
    f[f"{fn}/nether_border.mcfunction"] = mcfunction(
        "# Runs as a marker at spawn (it exists only for this function).",
        f"execute store result storage {NS}:rules border.x double 0.125 run data get entity @s Pos[0] 1",
        f"execute store result storage {NS}:rules border.z double 0.125 run data get entity @s Pos[2] 1",
        "kill @s",
        f"function {NS}:rules/nether_border_at with storage {NS}:rules border",
        f"execute in minecraft:the_nether run worldborder set {BORDER / 8}",
    )
    f[f"{fn}/nether_border_at.mcfunction"] = mcfunction(
        "$execute in minecraft:the_nether run worldborder center $(x) $(z)",
    )
    f[f"{fn}/second.mcfunction"] = mcfunction(
        "# Once a second. The End is closed until an admin runs realms:rules/open_end (rule 23).",
        f"execute unless score #end_open {OBJECTIVE} matches 1 in minecraft:the_end as @a[distance=0..] "
        f"run function {NS}:rules/leave_end",
        "# The welcome, a few seconds after a first join so the loading screen doesn't swallow it.",
        f"execute as @a[scores={{{WELCOME}=1}}] run function {NS}:rules/welcome",
        f"scoreboard players remove @a[scores={{{WELCOME}=2..}}] {WELCOME} 1",
        f"execute as @a[tag=!{JOINED}] run function {NS}:rules/first_join",
        "# Rule 26.",
        f"execute store result score #now {OBJECTIVE} run time query gametime",
        f"execute as @a[scores={{{END_GRACE}=1..}}] run function {NS}:rules/grace_end",
        f"execute as @a if score @s {GRACE} <= #now {OBJECTIVE} run function {NS}:rules/grace_end",
        "# The item goes with the grace (the launch and an admin's grace_end take both), it's off in the arena,",
        "# and it comes back after a death.",
        f"execute as @a if items entity @s armor.body {GRACE_ITEM} unless score @s {GRACE} > #now {OBJECTIVE} "
        "run item replace entity @s armor.body with minecraft:air",
        f"execute as @a[tag={ARENA}] if items entity @s armor.body {GRACE_ITEM} "
        "run item replace entity @s armor.body with minecraft:air",
        f"execute as @a[tag=!{ARENA}] if score @s {GRACE} > #now {OBJECTIVE} unless items entity @s armor.body * "
        f"run item replace entity @s armor.body with {GRACE_STACK}",
        f"execute as @e[{CORPSE}] if items entity @s armor.body {GRACE_ITEM} "
        "run item replace entity @s armor.body with minecraft:air",
        f"schedule function {NS}:rules/second 20t replace",
    )
    f[f"{fn}/first_join.mcfunction"] = mcfunction(
        "# Runs as a player the server hasn't seen before.",
        f"tag @s add {JOINED}",
        "# Someone who played here before this pack tagged anyone gets neither the welcome nor grace.",
        f"execute if predicate {NS}:rules/returning run return 0",
        f"scoreboard players set @s {WELCOME} {WELCOME_DELAY}",
        "# Rule 26: not in the launch hour, when the whole server starts together.",
        f"execute unless score #launching {OBJECTIVE} matches 1 run function {NS}:rules/grace_start",
    )
    f[f"{fn}/welcome.mcfunction"] = mcfunction(
        f"scoreboard players reset @s {WELCOME}",
        f"dialog show @s {NS}:welcome",
    )
    f[f"{fn}/grace_start.mcfunction"] = mcfunction(
        f"# Rule 26. Runs as the player; an admin can run it as one: execute as <player> run function "
        f"{NS}:rules/grace_start",
        f"execute store result score @s {GRACE} run time query gametime",
        f"scoreboard players add @s {GRACE} {GRACE_TICKS}",
        f"scoreboard players enable @s {END_GRACE}",
        "tellraw @s " + text(
            {"text": f"You have {GRACE_HOURS} hours of PvP grace: other players can't hurt you. ", "color": "green"},
            {"text": "Attacking a player ends it, and so does ", "color": "gray"},
            {"text": f"/trigger {END_GRACE}", "color": "aqua",
             "click_event": {"action": "suggest_command", "command": f"/trigger {END_GRACE}"}},
            {"text": ". Hours count while the server is running.", "color": "gray"}),
    )
    f[f"{fn}/grace_end.mcfunction"] = mcfunction(
        f"# Rule 26. Runs as the player: when the grace runs out, they attack a player or /trigger {END_GRACE}.",
        f"# An admin can end one: execute as <player> run function {NS}:rules/grace_end",
        f"scoreboard players reset @s {GRACE}",
        f"scoreboard players reset @s {END_GRACE}",
        f"execute if items entity @s armor.body {GRACE_ITEM} run item replace entity @s armor.body with minecraft:air",
        "tellraw @s " + text({"text": "Your PvP grace is over: other players can hurt you now.", "color": "red"}),
    )
    f[f"{fn}/grace_attack.mcfunction"] = mcfunction(
        "# A player with grace hurt a player (advancement realms:rules/grace_attack). Fights in the event",
        "# arena don't count.",
        f"advancement revoke @s only {NS}:rules/grace_attack",
        f"execute unless entity @s[tag={ARENA}] run function {NS}:rules/grace_end",
    )
    # 26.x conditions name their kind with "type" and entity predicates are components
    # ("minecraft:entity_type"); the pre-26 "condition" key fails the whole datapack load.
    f[f"data/{NS}/advancement/rules/grace_attack.json"] = js({
        "criteria": {"hurt_a_player": {"trigger": "minecraft:player_hurt_entity", "conditions": {
            "player": {"type": "minecraft:entity_scores", "entity": "this", "scores": {GRACE: {"min": 1}}},
            "entity": {"type": "minecraft:entity_properties", "entity": "this",
                       "predicate": {"minecraft:entity_type": "minecraft:player"}}}}},
        "rewards": {"function": f"{NS}:rules/grace_attack"},
    })
    # A player the server has seen before has left the game at least once, or (after a crash, which may not
    # count the leave) played for over a minute. Minecraft's own statistics go back before this pack.
    def stat_at_least(stat: str, least: int) -> dict:
        return {"type": "minecraft:entity_properties", "entity": "this", "predicate": {
            "minecraft:type_specific/player": {"stats": [
                {"type": "minecraft:custom", "stat": f"minecraft:{stat}", "value": {"min": least}}]}}}

    f[f"data/{NS}/predicate/rules/returning.json"] = js({"type": "minecraft:any_of", "terms": [
        stat_at_least("leave_game", 1), stat_at_least("play_time", 60 * 20)]})
    f[f"data/{NS}/enchantment/pvp_grace.json"] = js({
        "description": "PvP grace",
        "effects": {
            "minecraft:damage_immunity": [{"effect": {}, "requirements": {
                "type": "minecraft:damage_source_properties",
                "predicate": {"source_entity": {"minecraft:entity_type": "minecraft:player"}}}}],
            "minecraft:prevent_equipment_drop": {},
        },
        "slots": ["body"],
        "supported_items": [],
        "anvil_cost": 0, "max_cost": {"base": 0, "per_level_above_first": 0}, "max_level": 1,
        "min_cost": {"base": 0, "per_level_above_first": 0}, "weight": 1,
    })

    # The welcome notice and the pause menu's links (dialogs, Minecraft 1.21.6 and later).
    f[f"data/{NS}/dialog/welcome.json"] = js({
        "type": "minecraft:notice",
        "title": {"text": "Welcome to Monkey SMP", "color": "gold"},
        "body": [
            {"type": "minecraft:plain_message", "width": 300, "contents": (
                "A factions SMP: team up with up to three friends, claim land, and raid or defend it. "
                "You agreed to the short rules on the way in; the full rulebook is in the Discord.")},
            {"type": "minecraft:plain_message", "width": 300, "contents": (
                "Factions need members, and most start small. The recruiting posts in #smp-forum say who's "
                "looking.")},
            {"type": "minecraft:plain_message", "width": 300, "contents": [
                {"text": "Links to the Discord, the map, the rules and the store are in the pause menu, under "},
                {"text": "Monkey SMP", "color": "gold"}, {"text": "."}]},
        ],
        "action": {"label": "Join a faction: see who's recruiting", "width": 240,
                   "tooltip": "Opens the Monkey SMP Discord",
                   "action": {"type": "minecraft:open_url", "url": DISCORD}},
    })
    f[f"data/{NS}/dialog/links.json"] = js({
        "type": "minecraft:multi_action",
        "title": {"text": "Monkey SMP", "color": "gold"},
        "external_title": "Monkey SMP",
        "body": {"type": "minecraft:plain_message", "contents": "These open in your browser."},
        "columns": 2,
        "actions": [{"label": label, "tooltip": tooltip, "width": 140,
                     "action": {"type": "minecraft:open_url", "url": url}} for label, url, tooltip in LINKS],
        "exit_action": {"label": {"translate": "gui.back"}, "width": 200},
    })
    f["data/minecraft/tags/dialog/pause_screen_additions.json"] = js({"values": [f"{NS}:links"]})
    f[f"{fn}/leave_end.mcfunction"] = mcfunction(
        "# Runs as a player in the End while it's closed; the position is still the world spawn's x and z.",
        "execute in minecraft:overworld positioned over motion_blocking_no_leaves run tp @s ~ ~ ~",
        "tellraw @s " + text({"text": "The End is closed for now. ", "color": "red"},
                             {"text": "The owners will announce when it opens.", "color": "gray"}),
    )
    minutes = LAUNCH_SECONDS // 60
    f[f"{fn}/launch.mcfunction"] = mcfunction(
        f"# Rule 23. An admin runs this once, at launch: PvP and the Nether close for {minutes} minutes.",
        "gamerule pvp false",
        "gamerule allow_entering_nether_using_portals false",
        f"scoreboard players set #end_open {OBJECTIVE} 0",
        "# Rule 26: the season starts with nobody on grace (a test player's is gone), and nobody who first",
        "# joins in the launch hour gets one.",
        f"scoreboard players reset * {GRACE}",
        f"scoreboard players reset * {END_GRACE}",
        f"scoreboard players set #launching {OBJECTIVE} 1",
        f"schedule function {NS}:rules/launch_over {LAUNCH_SECONDS}s replace",
        announce(f"Welcome to Season I! PvP, the Nether and the End are closed for the first {minutes} minutes.",
                 "yellow"),
    )
    f[f"{fn}/launch_over.mcfunction"] = mcfunction(
        "# The launch hour is up: PvP and only the Nether open (rule 23).",
        "gamerule pvp true",
        "gamerule allow_entering_nether_using_portals true",
        f"scoreboard players set #launching {OBJECTIVE} 0",
        announce("The first hour is up: PvP and the Nether are open. The End stays closed for now.", "red"),
    )
    f[f"{fn}/open_end.mcfunction"] = mcfunction(
        f"scoreboard players set #end_open {OBJECTIVE} 1",
        announce("The End is open.", "light_purple"),
    )
    f[f"{fn}/close_end.mcfunction"] = mcfunction(
        f"scoreboard players set #end_open {OBJECTIVE} 0",
        announce("The End is closed.", "light_purple"),
    )

    # Ban B9.
    allowed = [f"minecraft:{e}" for e in VANILLA_NON_TREASURE if f"minecraft:{e}" not in BANNED_ENCHANTMENTS]
    f["data/minecraft/tags/enchantment/non_treasure.json"] = js({"replace": True, "values": allowed})
    # Fire Aspect's cooked drops come from this tag, not from its effects.
    f["data/minecraft/tags/enchantment/smelts_loot.json"] = js({"replace": True, "values": []})
    for name, numbers in DISABLED.items():
        f[f"data/minecraft/enchantment/{name}.json"] = js({
            "description": [{"translate": f"enchantment.minecraft.{name}"}, " (disabled)"],
            "effects": {},
            "slots": ["mainhand"],
            "supported_items": [],
            **numbers,
        })
    return f


def netherite_files() -> dict[str, str]:
    fn = f"data/{NS}/function/netherite"
    f: dict[str, str] = {
        "pack.mcmeta": pack_meta("Monkey SMP rule 24: no Netherite armor until the owners lift it"),
        "data/minecraft/tags/function/load.json": js({"values": [f"{NS}:netherite/load"]}),
        f"data/{NS}/tags/item/netherite_armor.json": js({"values": [f"minecraft:{i}" for i in NETHERITE_ARMOR]}),
    }
    for item in NETHERITE_ARMOR:
        f[f"data/minecraft/recipe/{item}_smithing.json"] = js(never(item))
    f[f"{fn}/load.mcfunction"] = mcfunction(
        "# Generated by tools/rules.py. Lift rule 24 with: datapack disable \"file/realms-no-netherite-armor\"",
        f"schedule function {NS}:netherite/second 20t replace",
    )
    f[f"{fn}/second.mcfunction"] = mcfunction(
        f"execute as @a at @s if items entity @s armor.* #{NS}:netherite_armor run function {NS}:netherite/take_off",
        f"schedule function {NS}:netherite/second 20t replace",
    )
    take_off = ["# Runs at a player wearing Netherite armor: each piece drops at their feet, as it was."]
    take_off += [f"execute if items entity @s armor.{slot} #{NS}:netherite_armor "
                 f"run function {NS}:netherite/drop_{slot}" for slot in ARMOR_SLOTS]
    take_off.append("tellraw @s " + text(
        {"text": "Netherite armor is off limits until the owners say otherwise (rule 24). ", "color": "red"},
        {"text": "Netherite tools and weapons are fine.", "color": "gray"}))
    f[f"{fn}/take_off.mcfunction"] = mcfunction(*take_off)
    for slot in ARMOR_SLOTS:
        f[f"{fn}/drop_{slot}.mcfunction"] = mcfunction(
            'summon minecraft:item ~ ~ ~ {Item:{id:"minecraft:stone"},PickupDelay:40,Tags:["realms.netherite"]}',
            f"item replace entity @n[type=minecraft:item,tag=realms.netherite] contents from entity @s armor.{slot}",
            "tag @n[type=minecraft:item,tag=realms.netherite] remove realms.netherite",
            f"item replace entity @s armor.{slot} with minecraft:air",
        )
    return f


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.realms / "datapacks" / RULES_PACK: rules_files(),
            repo.realms / "datapacks" / NETHERITE_PACK: netherite_files()}


def outputs(repo: Repo) -> dict[Path, bytes]:
    return {root / k: v.encode() for root, files in packs(repo).items() for k, v in files.items()}


def differences(repo: Repo) -> list[str]:
    want = outputs(repo)
    have = {p for r in packs(repo) if r.is_dir() for p in r.rglob("*") if p.is_file()}
    diff = [str(p.relative_to(repo.root)) for p, data in want.items() if not p.is_file() or p.read_bytes() != data]
    diff += [str(p.relative_to(repo.root)) + " (not generated)" for p in have - set(want)]
    return sorted(diff)


def write(repo: Repo) -> int:
    for r in packs(repo):
        shutil.rmtree(r, ignore_errors=True)
    for path, data in outputs(repo).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(outputs(repo))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Builds the Season I rules data packs.")
    ap.add_argument("--check", action="store_true", help="fail if the committed packs are out of date")
    args = ap.parse_args(argv)
    if args.check:
        diff = differences(REPO)
        if diff:
            print("rules packs are out of date (run python tools/rules.py):\n  " + "\n  ".join(diff))
            return 1
        print("rules packs are up to date")
        return 0
    print(f"wrote {write(REPO)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
