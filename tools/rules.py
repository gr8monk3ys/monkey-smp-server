"""Builds the data pack that makes the server enforce the relaunch's rules players shouldn't have to police.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)

It writes two folders, both generated (edit this file, not them). The rules are docs/relaunch/rules.md's; how hearts,
safe zones and claims work is docs/relaunch/lifesteal.md, and those are plugins (LifeStealZ, PvPManager,
GriefPrevention, WorldGuard), not this pack.

  package/monkey/datapacks/monkey-rules/
      The border: 6000 x 6000 centred on spawn (and the Nether's at 1:8), set once. Staff grow it by the
               season plan (docs/relaunch/season-1.md).
      The End: closed until Dragon Night, when staff run `function monkey:rules/open_end`.
      The launch: `function monkey:rules/launch` welcomes the season and starts its week-one tracking (the
               founder window, Server Firsts and challenges). PvP and the Nether are open from the start.
      Catch-up: a first join late in the season gets a starter kit (tools/catchup.py; off until staff turn it on).
      Onboarding: a welcome notice a few seconds after the first join (its one button: the Discord), and a
               Monkey SMP button in the pause menu with the Discord, map, rules and store links.

  package/monkey/datapacks/monkey-no-netherite-armor/
      The modded Season I's rule 24: no Netherite armor. The smithing table won't make it, and armor found in
      loot is taken off (it drops at the player's feet, nothing is lost). The relaunch has no such rule, so staff
      turn it off in the new world with `datapack disable "file/monkey-no-netherite-armor"`; the world remembers
      that across restarts and updates. (It stays in the repo while site/live-packs.json lists it.)

New players' protection is PvPManager's newbie protection (3 hours, 8 from week 4), not this pack. There is no
ban on Fire Aspect or Flame in the relaunch, so the pack no longer has one.

The installer copies both into the world on every install (Install-PackageDatapacks).
"""
import json
import re
from pathlib import Path

import catchup

from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta
from repo import REPO, Repo

RULES_PACK = "monkey-rules"
NETHERITE_PACK = "monkey-no-netherite-armor"

BORDER = 6000          # the starting border's full width in blocks, centred on spawn
TEAM_SIZE = 4          # the most players a finale team can have (docs/relaunch/season-1.md, "The finale")
OBJECTIVE = "monkey.rules"
# The no-Netherite-armor pack stamps the game time here every second while it is on, so other packs can tell it is
# (tools/firsts.py: full Netherite counts only once it is off). Disabling a pack runs nothing, so a stamp it is.
NETHERITE_BEAT = "#netherite_rule"

WELCOME = "monkey.welcome"           # seconds until the welcome shows (a first join is still loading)
WELCOME_DELAY = 3
JOINED = "monkey.joined"             # tag: seen before, so no welcome

# The welcome and the pause menu's links. The Discord invite and the map are site/config.json's.
DISCORD = "https://discord.gg/C25hy9Ca9W"
SITE = "https://monkeysmp.lscaturchio.xyz"
MAP = "https://map.monkeysmp.lscaturchio.xyz"
LINKS = (("Discord", DISCORD, "Events, teams and tickets"),
         ("Live map", MAP, "The world as it is, in your browser"),
         ("Rules", f"{SITE}/guide/rules", "The full rulebook on the website"),
         ("Store", f"{SITE}/#pricing", "The Server Pass and supporter tiers"))

# The server's Open Parties and Claims settings, which hold how many players a faction (a party) can have.
PARTIES_CONFIG = "config/openpartiesandclaims-server.toml"
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def faction_size(repo=REPO) -> int:
    """The most players a faction can have: maxPartyMembers in the Open Parties and Claims settings we ship."""
    text = (repo.defaults / PARTIES_CONFIG).read_text(encoding="utf-8")
    return int(re.search(r"(?m)^\s*maxPartyMembers\s*=\s*(\d+)\s*$", text).group(1))


def say_number(n: int) -> str:
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


ARMOR_SLOTS = ("head", "chest", "legs", "feet")
NETHERITE_ARMOR = ("netherite_helmet", "netherite_chestplate", "netherite_leggings", "netherite_boots")
# 26.2 can't drop a vanilla recipe (other data refers to it, and the server won't start), so the upgrade is
# replaced by one that needs a barrier as its template: no survival player can ever fill it in.
NEVER_TEMPLATE = "minecraft:barrier"


def never(item: str) -> dict:
    return {"type": "minecraft:smithing_transform", "addition": "#minecraft:netherite_tool_materials",
            "base": "minecraft:" + item.replace("netherite_", "diamond_"), "result": {"id": f"minecraft:{item}"},
            "template": NEVER_TEMPLATE}


def text(*parts: object) -> str:
    # Always a list, ASCII-escaped: unlike datapacks.text, kept so the committed rules pack doesn't change.
    return json.dumps(list(parts), separators=(",", ":"))


def js(obj) -> str:
    return json.dumps(obj, indent=2) + "\n"


def announce(message: str, color: str) -> str:
    return "tellraw @a " + text({"text": "[Monkey SMP] ", "color": "gold"}, {"text": message, "color": color})


def pack_meta(description: str) -> str:
    return mcmeta(f"{description} (generated by tools/rules.py)")


def rules_files() -> dict[str, str]:
    fn = f"data/{NS}/function/rules"
    f: dict[str, str] = {
        "pack.mcmeta": pack_meta("Monkey SMP rules: border, the End until Dragon Night, welcome and links"),
        "data/minecraft/tags/function/load.json": function_tag(f"{NS}:rules/load"),
    }
    f[f"{fn}/load.mcfunction"] = lines(
        "# Generated by tools/rules.py. Runs on every start and /reload.",
        f"scoreboard objectives add {OBJECTIVE} dummy",
        f"scoreboard objectives add {WELCOME} dummy",
        f"function {NS}:catchup/load",
        "# The border, once per world: after that it is the staff's to grow.",
        f"execute unless score #border {OBJECTIVE} matches 1 run function {NS}:rules/border",
        f"schedule function {NS}:rules/second 20t replace",
    )
    f[f"{fn}/border.mcfunction"] = lines(
        "# A function run by the server runs at the world spawn, so ~ ~ is spawn.",
        "execute in minecraft:overworld run worldborder center ~ ~",
        f"execute in minecraft:overworld run worldborder set {BORDER}",
        "# On 26.2 each dimension has its own border (the Nether's no longer follows the overworld's), so",
        "# give the Nether the one it used to have: the same area at its 1:8 scale.",
        f"execute summon minecraft:marker run function {NS}:rules/nether_border",
        f"scoreboard players set #border {OBJECTIVE} 1",
    )
    f[f"{fn}/nether_border.mcfunction"] = lines(
        "# Runs as a marker at spawn (it exists only for this function).",
        f"execute store result storage {NS}:rules border.x double 0.125 run data get entity @s Pos[0] 1",
        f"execute store result storage {NS}:rules border.z double 0.125 run data get entity @s Pos[2] 1",
        "kill @s",
        f"function {NS}:rules/nether_border_at with storage {NS}:rules border",
        f"execute in minecraft:the_nether run worldborder set {BORDER / 8}",
    )
    f[f"{fn}/nether_border_at.mcfunction"] = lines(
        "$execute in minecraft:the_nether run worldborder center $(x) $(z)",
    )
    f[f"{fn}/second.mcfunction"] = lines(
        "# Once a second. The End is closed until staff run monkey:rules/open_end on Dragon Night.",
        f"execute unless score #end_open {OBJECTIVE} matches 1 in minecraft:the_end as @a[distance=0..] "
        f"run function {NS}:rules/leave_end",
        "# The welcome, a few seconds after a first join so the loading screen doesn't swallow it.",
        f"execute as @a[scores={{{WELCOME}=1}}] run function {NS}:rules/welcome",
        f"scoreboard players remove @a[scores={{{WELCOME}=2..}}] {WELCOME} 1",
        f"execute as @a[tag=!{JOINED}] run function {NS}:rules/first_join",
        f"schedule function {NS}:rules/second 20t replace",
    )
    f[f"{fn}/first_join.mcfunction"] = lines(
        "# Runs as a player the server hasn't seen before.",
        f"tag @s add {JOINED}",
        "# Someone who played here before this pack tagged anyone gets neither the welcome nor the kit.",
        f"execute if predicate {NS}:rules/returning run return 0",
        f"scoreboard players set @s {WELCOME} {WELCOME_DELAY}",
        f"function {NS}:catchup/first_join",
    )
    f[f"{fn}/welcome.mcfunction"] = lines(
        f"scoreboard players reset @s {WELCOME}",
        f"dialog show @s {NS}:welcome",
        "# A late first join's kit came while they were loading; say so now (tools/catchup.py).",
        f"execute if score @s {catchup.KIT_DONE} matches 1 run function {NS}:catchup/note",
    )

    # A player the server has seen before has left the game at least once, or (after a crash, which may not
    # count the leave) played for over a minute. Minecraft's own statistics go back before this pack.
    def stat_at_least(stat: str, least: int) -> dict:
        return {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {
            "minecraft:type_specific/player": {"stats": [
                {"type": "minecraft:custom", "stat": f"minecraft:{stat}", "value": {"min": least}}]}}}

    f[f"data/{NS}/predicate/rules/returning.json"] = js({"condition": "minecraft:any_of", "terms": [
        stat_at_least("leave_game", 1), stat_at_least("play_time", 60 * 20)]})

    # The welcome notice and the pause menu's links (dialogs, Minecraft 1.21.6 and later).
    f[f"data/{NS}/dialog/welcome.json"] = js({
        "type": "minecraft:notice",
        "title": {"text": "Welcome to Monkey SMP", "color": "gold"},
        "body": [
            {"type": "minecraft:plain_message", "width": 300, "contents": (
                "A lifesteal SMP: kill a player and you take one of their hearts. Mobs, falls and lava cost you "
                "nothing. At 0 hearts you're out for 24 hours, then back with 3.")},
            {"type": "minecraft:plain_message", "width": 300, "contents": (
                "Claim your base with a golden shovel to keep it safe from griefing and theft; fights can still "
                "happen there. Spawn and the market are safe zones, and you have a few hours of protection "
                "to settle in.")},
            {"type": "minecraft:plain_message", "width": 300, "contents": (
                f"The season ends in a finale for teams of up to {say_number(TEAM_SIZE)}. You agreed to the "
                "short rules on the way in; the full rulebook is on the website.")},
            {"type": "minecraft:plain_message", "width": 300, "contents": [
                {"text": "Links to the Discord, the map, the rules and the store are in the pause menu, under "},
                {"text": "Monkey SMP", "color": "gold"}, {"text": "."}]},
        ],
        "action": {"label": "Join the Discord", "width": 240,
                   "tooltip": "Events, teams and tickets: opens the Monkey SMP Discord",
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
    f[f"{fn}/leave_end.mcfunction"] = lines(
        "# Runs as a player in the End while it's closed; the position is still the world spawn's x and z.",
        "execute in minecraft:overworld positioned over motion_blocking_no_leaves run tp @s ~ ~ ~",
        "tellraw @s " + text({"text": "The End is closed until Dragon Night. ", "color": "red"},
                             {"text": "Staff will announce it.", "color": "gray"}),
    )
    f.update(catchup.datapack_files())
    f[f"{fn}/launch.mcfunction"] = lines(
        "# Staff run this once, at launch. PvP and the Nether are open from the start; the End waits for",
        "# Dragon Night.",
        f"scoreboard players set #end_open {OBJECTIVE} 0",
        announce("Welcome to the new season! PvP and the Nether are open. The End opens on Dragon Night.",
                 "yellow"),
        "# The launch weekend opens for Founder's Circlet (tools/wardrobe.py), and this week's challenges start",
        "# from zero, so test play before the launch doesn't count (tools/challenges.py). Only the first launch",
        "# opens it: challenges/launch sets #launched, and a launch run again by mistake after the weekend would",
        "# open a window that no wall-clock sync closes any more.",
        f"execute unless score {LAUNCHED} matches 1 run function {NS}:wardrobe/founder/open",
        "# Server Firsts (tools/firsts.py): a first claimed before the first launch is cleared. Before",
        "# challenges/launch, which sets #launched.",
        f"function {NS}:firsts/launch",
        f"function {NS}:challenges/launch",
    )
    f[f"{fn}/open_end.mcfunction"] = lines(
        f"scoreboard players set #end_open {OBJECTIVE} 1",
        announce("The End is open.", "light_purple"),
    )
    f[f"{fn}/close_end.mcfunction"] = lines(
        f"scoreboard players set #end_open {OBJECTIVE} 0",
        announce("The End is closed.", "light_purple"),
    )
    return f


def netherite_files() -> dict[str, str]:
    fn = f"data/{NS}/function/netherite"
    f: dict[str, str] = {
        "pack.mcmeta": pack_meta("Monkey SMP rule 24: no Netherite armor until the owners lift it"),
        "data/minecraft/tags/function/load.json": function_tag(f"{NS}:netherite/load"),
        f"data/{NS}/tags/item/netherite_armor.json": js({"values": [f"minecraft:{i}" for i in NETHERITE_ARMOR]}),
    }
    for item in NETHERITE_ARMOR:
        f[f"data/minecraft/recipe/{item}_smithing.json"] = js(never(item))
    f[f"{fn}/load.mcfunction"] = lines(
        "# Generated by tools/rules.py. Lift rule 24 with: datapack disable \"file/monkey-no-netherite-armor\"",
        f"scoreboard objectives add {OBJECTIVE} dummy",
        f"schedule function {NS}:netherite/second 20t replace",
    )
    f[f"{fn}/second.mcfunction"] = lines(
        f"# The stamp ({NETHERITE_BEAT}) says the rule holds; it goes stale once the pack is off.",
        f"execute store result score {NETHERITE_BEAT} {OBJECTIVE} run time query gametime",
        f"execute as @a at @s if items entity @s armor.* #{NS}:netherite_armor run function {NS}:netherite/take_off",
        f"schedule function {NS}:netherite/second 20t replace",
    )
    take_off = ["# Runs at a player wearing Netherite armor: each piece drops at their feet, as it was."]
    take_off += [f"execute if items entity @s armor.{slot} #{NS}:netherite_armor "
                 f"run function {NS}:netherite/drop_{slot}" for slot in ARMOR_SLOTS]
    take_off.append("tellraw @s " + text(
        {"text": "Netherite armor is off limits until the owners say otherwise (rule 24). ", "color": "red"},
        {"text": "Netherite tools and weapons are fine.", "color": "gray"}))
    f[f"{fn}/take_off.mcfunction"] = lines(*take_off)
    for slot in ARMOR_SLOTS:
        f[f"{fn}/drop_{slot}.mcfunction"] = lines(
            'summon minecraft:item ~ ~ ~ {Item:{id:"minecraft:stone"},PickupDelay:40,Tags:["monkey.netherite"]}',
            f"item replace entity @n[type=minecraft:item,tag=monkey.netherite] contents from entity @s armor.{slot}",
            "tag @n[type=minecraft:item,tag=monkey.netherite] remove monkey.netherite",
            f"item replace entity @s armor.{slot} with minecraft:air",
        )
    return f


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / RULES_PACK: rules_files(),
            repo.monkey / "datapacks" / NETHERITE_PACK: netherite_files()}

