"""Server Firsts: the first player on the server to reach each of the season's milestones keeps it for the season.

    python tools/datapacks.py                          regenerate the monkey-firsts data pack (with the others)
    python tools/firsts.py list WORLD                  every first and who holds it, from the saved world
    python tools/firsts.py champion WORLD --season 1   who has the most (the season title), and the staff commands

What players see: the first to do one of MILESTONES (enter the Nether, find a bastion, slay the dragon...) is
announced to everyone in chat, with a title on screen and a sound, and keeps it for the season. `/trigger firsts`
lists every milestone and who holds it. At the season's end the player with the most firsts gets a title
(TITLE, set up by staff: docs/SEASONS.md, "Ending a season"). A tie goes to whoever reached that number first.

How it works: one hidden advancement per milestone, with vanilla's own trigger (the same criteria as the
vanilla advancement it mirrors), that fires only once Season I has launched (`#launched rw.day`, set by
`monkey:rules/launch`), only while nobody holds that first and the season isn't locked (`#season_locked`,
events' season/lock), and the End one only while the End is open. Its reward function checks all that again and
the rest (not in the event arena, not in creative or spectator, Netherite armor allowed, and for an item a player
was carrying since test play: see CLEAN) and claims it. A claim is
kept twice, for the tools: in command storage `monkey:firsts held.<id>` ({name, order, week}: the holder's name,
1 for the season's first claim and so on, and the challenge week it fell in) and as the score `rf.<id>` of the
holder (the same order). `holders(world)` reads them from the saved world (feature code such as the weekly
recap uses it: "firsts this week" is `claimed_in(holders(world), week)`).

Nothing is sold and nothing helps in a fight: a first is a line in chat and, for the most firsts, a title.
Banned things are never milestones (no totems, crystals or pearls), and full Netherite only counts once the
owners lift rule 24 (the monkey-no-netherite-armor pack, while it is on, stamps the game time every second:
NETHERITE_BEAT; a stamp under NETHERITE_STALE ticks old means the rule still holds).
Test play doesn't count: nothing fires before the launch, the first `rules/launch` of a world clears any
first claimed by hand before it (`monkey:firsts/launch`), and an item first (diamond, debris, mace, elytra)
counts only for a player seen after the launch without that item on them (CLEAN), so one kept from test play
doesn't claim it.

The data pack (package/monkey/datapacks/monkey-firsts/, generated: edit this file, not it) has the staff
commands too (docs/ADMIN.md, "Server Firsts"). Stdlib only. Unlike most of tools/ (Python 3.11+,
docs/MAINTAINING.md) this file runs on Python 3.10 too, as drops.py does, because staff run `list` and
`champion` on the VPS, whose python3 may be 3.10: it reads only saved_world's scoreboard and command storage,
never its 3.11-only Open Parties and Claims reader (tomllib).
"""
import argparse
import json
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import saved_world
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, score_check, text
from events import ARENA_TAG
from events import STATE as EVENTS
from repo import Repo
from rules import NETHERITE_BEAT
from rules import OBJECTIVE as RULES
from season import mc_string

DATAPACK = "monkey-firsts"
FN = f"data/{NS}/function/firsts"
ADVANCEMENT = f"data/{NS}/advancement/firsts"
STORE = f"{NS}:firsts"
KEY = "firsts"              # STORE's key in the namespace's command storage file
OBJ = "rf"                  # #<id>: 1 once claimed; #claimed: how many claims so far this season;
                            # #unnamed: 1 while a claim waits for its holder's name; #wait: seconds
                            # since second last ran rename
RENAME_SECONDS = 10         # how often a claim without its holder's name is read again
TRIGGER = "firsts"
NAME_TAG = "rf.name"        # the item display that reads a holder's name for a moment
NETHERITE_STALE = 100       # ticks: an older stamp means the no-Netherite-armor pack is off
TITLE = ("title_pioneer_s{season}", "aqua", "[S{season} Pioneer] ")   # team, color, prefix (season.py carries title_*)
SEASON_LOCKED = "#season_locked"   # in EVENTS: 1 once events' season/lock has locked the world at the season's end
# An item first counts for a player only once they have been seen after the launch without that item on them
# (the tag CLEAN + id, kept in their player data): one carried over from test play never claims it. Checked at
# the launch and every second after it, for the slots inventory_changed watches (inventory, armor, offhand).
CLEAN = "rf.clean."
ITEM_SLOTS = ("container.*", "armor.*", "weapon.offhand")

# ---------------------------------------------------------------- the milestones: edit here
#
# id        stable and short: it names the first's advancement, storage and score (rf.<id>); never rename one
#           mid-season
# name      the menu line and the announcement ("Steve is the first on the server to enter the Nether")
# about     the hover text: what counts
# trigger, conditions   the advancement's criterion, as vanilla's advancement in `mirrors` has it (26.3)
# player    a predicate on the player, added to the launched-and-unclaimed check
# end       only while the End is open (rule 23: monkey:rules/open_end); netherite: only once rule 24 is lifted
# item      an item first (holding()): it counts only for a player not carrying it over from test play (CLEAN)
# reopen    what staff should know before reopening it (the menu and docs/ADMIN.md say the rest)
# Listed roughly in the order a season reaches them.


def holding(item: str) -> dict:
    """An item first: inventory_changed while it is on the player (the item names its CLEAN tag)."""
    return {"trigger": "inventory_changed", "conditions": {"items": [{"items": f"minecraft:{item}"}]}, "item": item}


def killed(mob: str) -> dict:
    return {"entity": {"type": "minecraft:entity_properties", "entity": "this",
                       "predicate": {"minecraft:entity_type": f"minecraft:{mob}"}}}


def inside(structure: str) -> dict:
    return {"type": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:location": {"structures": f"minecraft:{structure}"}}}


FULL_NETHERITE = {"type": "minecraft:entity_properties", "entity": "this", "predicate": {"minecraft:equipment": {
    slot: {"items": f"minecraft:netherite_{piece}"}
    for slot, piece in (("head", "helmet"), ("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots"))}}}

MILESTONES = [
    dict(id="diamond", name="Find a diamond", mirrors="story/mine_diamond",
         about="Hold a diamond: mined, looted or traded.", **holding("diamond")),
    dict(id="nether", name="Enter the Nether", mirrors="story/enter_the_nether",
         about="Go through a Nether portal (after the launch hour).",
         trigger="changed_dimension", conditions={"to": "minecraft:the_nether"}),
    dict(id="fortress", name="Find a Nether fortress", mirrors="nether/find_fortress",
         about="Set foot in a Nether fortress.", trigger="location", player=inside("fortress")),
    dict(id="bastion", name="Find a bastion", mirrors="nether/find_bastion",
         about="Set foot in a bastion remnant.", trigger="location", player=inside("bastion_remnant")),
    dict(id="debris", name="Find ancient debris", mirrors="nether/obtain_ancient_debris",
         about="Hold a block of ancient debris.", **holding("ancient_debris")),
    dict(id="vault", name="Open a trial vault", mirrors="adventure/under_lock_and_key",
         about="Use a trial key (or an ominous one) on a vault in trial chambers.", trigger="item_used_on_block",
         conditions={"location": {"type": "minecraft:all_of", "terms": [
             {"type": "minecraft:location_check", "predicate": {"block": {"blocks": "minecraft:vault"}}},
             {"type": "minecraft:match_tool",
              "predicate": {"items": ["minecraft:trial_key", "minecraft:ominous_trial_key"]}}]}}),
    dict(id="mace", name="Get a mace", mirrors=None,
         about="Hold a mace, from an ominous vault's heavy core. Enchanted maces stay banned (B2).",
         **holding("mace")),
    dict(id="raid", name="Win a raid", mirrors="adventure/hero_of_the_village",
         about="Defend a village through a whole raid.", trigger="hero_of_the_village"),
    dict(id="wither", name="Defeat the Wither", mirrors=None,
         about="Land the killing blow on a Wither.", trigger="player_killed_entity", conditions=killed("wither")),
    dict(id="beacon", name="Light a beacon", mirrors="nether/create_beacon",
         about="Build a beacon on a pyramid so it shines.", trigger="construct_beacon",
         conditions={"level": {"min": 1}}),
    dict(id="end", name="Enter the End", mirrors="story/enter_the_end", end=True,
         about="Go through an End portal once the End opens (Dragon Night).",
         trigger="changed_dimension", conditions={"to": "minecraft:the_end"}),
    dict(id="dragon", name="Slay the dragon", mirrors="end/kill_dragon",
         about="Land the killing blow on the Ender Dragon.", trigger="player_killed_entity",
         conditions=killed("ender_dragon"),
         reopen="Players can't bring the dragon back (end crystals are banned), so a reopened dragon stays open "
                "until staff respawn it by hand. To move it to the right player, reopen it and run claim/dragon "
                "as them."),
    dict(id="elytra", name="Find an elytra", mirrors="end/elytra",
         about="Hold an elytra, from an End ship.", **holding("elytra")),
    dict(id="netherite", name="Wear full Netherite", mirrors=None, netherite=True,
         about="Wear all four pieces of Netherite armor, once the owners lift rule 24 (the Netherite age).",
         trigger="location", player=FULL_NETHERITE),
]
NAME_MAX = 24   # a milestone's name, so its menu line (name, holder, week) fits one line of chat


def milestone(first_id: str) -> dict | None:
    return next((m for m in MILESTONES if m["id"] == first_id), None)


# ---------------------------------------------------------------- reading the saved world


@dataclass(frozen=True)
class First:
    id: str            # MILESTONES' id
    milestone: str     # its name as players see it (the id itself for one no longer listed)
    player: str        # the holder's name
    order: int         # 1 for the season's first claim, then 2, 3...
    week: int | None   # the challenge week it was claimed in (tools/season_calendar.py's); None when unknown


def holders(world: Path, scores: dict[str, dict[str, int]] | None = None) -> list[First]:
    """Every first claimed in the saved world, in the order they were claimed (empty before any).

    Read from command storage monkey:firsts held.<id> ({name, order, week}); a holder whose name isn't there
    (storage not saved yet, or the in-game name lookup failed) is taken from the scores rf.<id>. A file not
    shaped as the server saves it is a ValueError (saved_world's). `scores`: the saved scoreboard's scores, when
    the caller has read them already."""
    storage = saved_world.command_storage(world, NS) or {}
    claims = storage.get(KEY, {}).get("held", {})
    if not isinstance(claims, dict):
        claims = {}
    if scores is None:
        board = saved_world.scoreboard(world)
        scores = board.scores if board else {}
    ids = [m["id"] for m in MILESTONES] + sorted(set(claims) - {m["id"] for m in MILESTONES})
    found = []
    for first_id in ids:
        entry = claims.get(first_id) if isinstance(claims.get(first_id), dict) else {}
        by_score = {name: order for name, order in scores.get(f"{OBJ}.{first_id}", {}).items() if order > 0}
        player = entry.get("name") if isinstance(entry.get("name"), str) else ""
        order = entry.get("order") if isinstance(entry.get("order"), int) else 0
        if not player and by_score:
            player, order = min(by_score.items(), key=lambda kv: kv[1])
        if not player:
            continue
        if order <= 0:
            order = by_score.get(player, 0)
        week = entry.get("week")
        m = milestone(first_id)
        found.append(First(first_id, m["name"] if m else first_id, player, order,
                           week if isinstance(week, int) and week >= 0 else None))
    return sorted(found, key=lambda f: (f.order <= 0, f.order, ids.index(f.id)))


def claimed_in(firsts: list[First], week: int) -> list[First]:
    """Of holders()' list, the firsts claimed in challenge week `week` (season_calendar.week_at), in claim order."""
    return [f for f in firsts if f.week == week]


@dataclass(frozen=True)
class Standing:
    player: str
    count: int      # firsts held
    reached: int    # the order of their latest first: when they reached `count` (lower is earlier)


def standings(firsts: list[First]) -> list[Standing]:
    """Players by firsts held, most first; a tie goes to whoever reached that number first."""
    count = Counter(f.player for f in firsts)
    reached = {p: max(f.order for f in firsts if f.player == p) for p in count}
    return sorted((Standing(p, n, reached[p]) for p, n in count.items()),
                  key=lambda s: (-s.count, s.reached, s.player.lower()))


def champion(firsts: list[First]) -> Standing | None:
    """Who gets the season title: the most firsts, the earliest to reach that number. None before any first."""
    table = standings(firsts)
    return table[0] if table else None


# ---------------------------------------------------------------- the data pack


LAUNCHED_HOLDER, LAUNCHED_OBJECTIVE = LAUNCHED.split()


def advancement(m: dict) -> dict:
    """A hidden advancement: vanilla's criterion for the milestone, checked only after the launch, before the
    season's lock and while nobody holds the first (so it costs next to nothing once it is claimed). The reward
    checks again and claims it.

    26.x shapes, as tools/challenges.py's: a condition names its kind with "type", a criterion's "player" is
    one condition (not a list), and entity predicates are components."""
    terms = [score_check(LAUNCHED_HOLDER, LAUNCHED_OBJECTIVE, least=1), score_check(f"#{m['id']}", OBJ, most=0),
             score_check(SEASON_LOCKED, EVENTS, most=0)]
    if m.get("end"):
        terms.append(score_check("#end_open", RULES, least=1))
    if m.get("player"):
        terms.append(m["player"])
    conditions = {**m.get("conditions", {}), "player": {"type": "minecraft:all_of", "terms": terms}}
    return {"criteria": {m["id"]: {"trigger": f"minecraft:{m['trigger']}", "conditions": conditions}},
            "rewards": {"function": f"{NS}:firsts/got/{m['id']}"}}


def head_loot_table() -> dict:
    """A player head of whoever the loot command runs as: its profile has their name."""
    return {"type": "minecraft:chest", "pools": [{"rolls": 1, "entries": [{
        "type": "minecraft:item", "name": "minecraft:player_head",
        "modifier": {"type": "minecraft:fill_player_head", "entity": "this"}}]}]}


def held(first_id: str, field: str, color: str) -> dict:
    return {"storage": STORE, "nbt": f"held.{first_id}.{field}", "color": color}


OPEN = {"text": "[All firsts]", "color": "aqua", "underlined": True,
        "click_event": {"action": "run_command", "command": f"/trigger {TRIGGER}"}}


def phrase(m: dict) -> str:
    """The name as it reads mid-sentence: "enter the Nether"."""
    return m["name"][0].lower() + m["name"][1:]


def got_function(m: dict) -> str:
    fid = m["id"]
    out = [f"# {m['name']}: the advancement fired. It is taken back first, so it can fire again if this didn't",
           "# count; once the first is claimed its condition stops it firing at all.",
           f"advancement revoke @s only {NS}:firsts/{fid}",
           f"execute if score #{fid} {OBJ} matches 1.. run return 0",
           f"execute unless score {LAUNCHED} matches 1 run return 0",
           "# Not once the season is locked (the finale: adventure mode, the world archived).",
           f"execute if score {SEASON_LOCKED} {EVENTS} matches 1 run return 0",
           "# Not with kit gear in the event arena, and not in creative or spectator (staff).",
           f"execute if entity @s[tag={ARENA_TAG}] run return 0",
           "execute unless entity @s[gamemode=!creative,gamemode=!spectator] run return 0"]
    if m.get("end"):
        out += ["# Only while the End is open (the advancement checks it too).",
                f"execute unless score #end_open {RULES} matches 1.. run return 0"]
    if m.get("item"):
        out += [f"# Not for {m['item'].replace('_', ' ')} carried over from test play: this player must have been seen",
                "# without one on them since the launch (monkey:firsts/clean).",
                f"execute unless entity @s[tag={CLEAN}{fid}] run return 0"]
    if m.get("netherite"):
        out += [f"# Rule 24: while monkey-no-netherite-armor is on it stamps {NETHERITE_BEAT} every second, and",
                "# takes the armor off within one. No stamp at all (no such pack): the rule isn't there.",
                f"execute store result score #age {OBJ} run time query gametime",
                f"scoreboard players operation #age {OBJ} -= {NETHERITE_BEAT} {RULES}",
                f"execute if score #age {OBJ} matches ..{NETHERITE_STALE} run return 0"]
    out.append(f"function {NS}:firsts/claim/{fid}")
    return lines(*out)


def claim_function(m: dict) -> str:
    fid = m["id"]
    return lines(
        f"# {m['name']}: this player is the first. Staff can run it as a player to make good an outage (at",
        f"# them: the name is read where they stand): execute as NAME at @s run function {NS}:firsts/claim/{fid}",
        f"execute if score #{fid} {OBJ} matches 1.. run return 0",
        f"scoreboard players set #{fid} {OBJ} 1",
        f"scoreboard players add #claimed {OBJ} 1",
        f"scoreboard players operation @s {OBJ}.{fid} = #claimed {OBJ}",
        f"function {NS}:firsts/name",
        f"data modify storage {STORE} held.{fid} set value {{name:\"\",order:0,week:-1}}",
        f"data modify storage {STORE} held.{fid}.name set from storage {STORE} name",
        f"execute store result storage {STORE} held.{fid}.order int 1 run scoreboard players get #claimed {OBJ}",
        f"execute store result storage {STORE} held.{fid}.week int 1 run scoreboard players get #week rc.week",
        "# The name can't be read where no chunk is loaded (as the player changes dimension): second fills it in.",
        f"execute if data storage {STORE} held.{fid}{{name:\"\"}} run scoreboard players set #unnamed {OBJ} 1",
        "tellraw @a " + text("", {"text": "Server First! ", "color": "gold", "bold": True},
                             {"selector": "@s", "color": "yellow"},
                             {"text": " is the first on the server to ", "color": "gold"},
                             {"text": phrase(m), "color": "yellow", "hover_event": {"action": "show_text",
                                                                                     "value": m["about"]}},
                             {"text": ". ", "color": "gold"}, OPEN),
        "title @a subtitle " + text("", {"selector": "@s", "color": "yellow"},
                                    {"text": f": {m['name']}", "color": "white"}),
        "title @a title " + text({"text": "Server First", "color": "gold", "bold": True}),
        "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1",
    )


def clean_function() -> str:
    """Tags each online player who has no item first's item on them (CLEAN). From the launch on."""
    out = ["# Each item first counts for a player only once they have been seen without its item since the launch,",
           "# so one carried over from test play doesn't claim it. Run at the launch and every second after it."]
    for m in MILESTONES:
        if m.get("item"):
            missing = " ".join(f"unless items entity @s {slot} minecraft:{m['item']}" for slot in ITEM_SLOTS)
            out.append(f"execute as @a[tag=!{CLEAN}{m['id']}] {missing} run tag @s add {CLEAN}{m['id']}")
    return lines(*out)


def show_function(m: dict) -> str:
    """The milestone's line in /trigger firsts, read as holders() reads the saved world: the name from storage,
    else the holder by their rf.<id> score (online only: a pack can't print an offline score holder), and no
    week when it is unknown (-1)."""
    fid = m["id"]
    hover = {"action": "show_text", "value": m["about"]}
    name = {"text": m["name"], "color": "green", "hover_event": hover}
    out = [f"# {m['name']}: its line in /trigger firsts (one tellraw of the six runs).",
           f"execute unless score #{fid} {OBJ} matches 1.. run return run tellraw @s " + text(
               " ", {**name, "color": "white"}, {"text": "  open", "color": "gray"}),
           f"execute store success score #named {OBJ} if data storage {STORE} held.{fid}.name",
           f'execute if data storage {STORE} held.{fid}{{name:""}} run scoreboard players set #named {OBJ} 0',
           f"execute store success score #dated {OBJ} if data storage {STORE} held.{fid}.week",
           f"execute if data storage {STORE} held.{fid}{{week:-1}} run scoreboard players set #dated {OBJ} 0"]
    holder = f"@a[scores={{{OBJ}.{fid}=1..}}]"
    who = [(f"if score #named {OBJ} matches 1", held(fid, "name", "yellow")),
           (f"if score #named {OBJ} matches 0 if entity {holder}", {"selector": holder, "color": "yellow"}),
           ("", {"text": "a player now offline", "color": "gray"})]
    when = [(f"if score #dated {OBJ} matches 1", [{"text": "  week ", "color": "dark_gray"},
                                                   held(fid, "week", "dark_gray")]),
            ("", [])]
    for who_if, who_part in who:
        for when_if, when_parts in when:
            cmd = "tellraw @s " + text(" ", name, {"text": "  ", "color": "gray"}, who_part, *when_parts)
            cond = " ".join(c for c in (who_if, when_if) if c)
            out.append(f"execute {cond} run return run {cmd}" if cond else cmd)
    return lines(*out)


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP Server Firsts: the first to each milestone (generated by tools/firsts.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:firsts/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:firsts/tick")
    f[f"data/{NS}/loot_table/firsts/head.json"] = json.dumps(head_loot_table(), indent=2)

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/firsts.py. Scores and storage are kept across restarts.",
        f"scoreboard objectives add {TRIGGER} trigger",
        f"scoreboard objectives add {OBJ} dummy",
        *(f"scoreboard objectives add {OBJ}.{m['id']} dummy" for m in MILESTONES),
        "# 0 for a first nobody holds yet (the advancements read it), without touching a claimed one.",
        *(f"scoreboard players add #{m['id']} {OBJ} 0" for m in MILESTONES),
        f"scoreboard players add #claimed {OBJ} 0",
        "# A claim stored without its name by an older pack never set #unnamed: rename checks them all once.",
        f"scoreboard players set #unnamed {OBJ} 1",
        f"schedule function {NS}:firsts/second 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"scoreboard players enable @a {TRIGGER}",
        f"execute if score {LAUNCHED} matches 1 run function {NS}:firsts/clean",
        f"# Every {RENAME_SECONDS} seconds, not every second: a holder can stay offline for days.",
        f"scoreboard players add #wait {OBJ} 1",
        f"execute if score #wait {OBJ} matches {RENAME_SECONDS}.. if score #unnamed {OBJ} matches 1.. "
        f"run function {NS}:firsts/rename",
        f"execute if score #wait {OBJ} matches {RENAME_SECONDS}.. run scoreboard players set #wait {OBJ} 0",
        f"schedule function {NS}:firsts/second 20t replace",
    )
    f[f"{FN}/rename.mcfunction"] = lines(
        "# A first claimed without its holder's name (the read failed): read it again where the holder stands",
        "# once they are online, and keep #unnamed set while any is still missing.",
        f"scoreboard players set #unnamed {OBJ} 0",
        *(f"function {NS}:firsts/rename/one {{id:\"{m['id']}\"}}" for m in MILESTONES),
    )
    f[f"{FN}/rename/one.mcfunction"] = lines(
        "# Macro {id}: the first's name read again where its holder stands, if it has none and they're online.",
        f"$execute unless data storage {STORE} held.$(id){{name:\"\"}} run return 0",
        "# Cleared first: with the holder offline nothing is read, and another player's name must not be kept.",
        f"data modify storage {STORE} name set value \"\"",
        f"$execute as @a[scores={{{OBJ}.$(id)=1..}},limit=1] at @s run function {NS}:firsts/name",
        f"$data modify storage {STORE} held.$(id).name set from storage {STORE} name",
        f"$execute if data storage {STORE} held.$(id){{name:\"\"}} run scoreboard players set #unnamed {OBJ} 1",
    )
    f[f"{FN}/tick.mcfunction"] = lines(f"execute as @a[scores={{{TRIGGER}=1..}}] run function {NS}:firsts/use")
    f[f"{FN}/name.mcfunction"] = lines(
        f"# Puts this player's name in storage {STORE} name (\"\" if it can't), through a player head of them",
        "# on an item display that exists only for this function.",
        f"data modify storage {STORE} name set value \"\"",
        f"summon minecraft:item_display ~ ~ ~ {{Tags:[\"{NAME_TAG}\"]}}",
        f"loot replace entity @n[type=minecraft:item_display,tag={NAME_TAG}] contents loot {NS}:firsts/head",
        f"data modify storage {STORE} name set from entity @n[type=minecraft:item_display,tag={NAME_TAG}] "
        'item.components."minecraft:profile".name',
        f"kill @e[type=minecraft:item_display,tag={NAME_TAG}]",
    )
    f[f"{FN}/launch.mcfunction"] = lines(
        "# Run by monkey:rules/launch before challenges/launch sets #launched. At a world's first launch, a",
        "# first claimed before it (by hand, in test play) is cleared; a launch run again later clears nothing.",
        f"execute if score {LAUNCHED} matches 1 run return 0",
        f"function {NS}:firsts/clear",
        "# Whoever is online now without an item first's item can claim it from the start (no one-second gap).",
        f"function {NS}:firsts/clean",
    )
    f[f"{FN}/clean.mcfunction"] = clean_function()
    f[f"{FN}/clear.mcfunction"] = lines(
        "# Every first open again, the count from zero. Staff: only on a test server (docs/ADMIN.md).",
        f"data remove storage {STORE} held",
        f"scoreboard players set #claimed {OBJ} 0",
        *(f"function {NS}:firsts/reopen/{m['id']}" for m in MILESTONES),
    )

    count = [f"scoreboard players set @s {OBJ} 0"]
    count += [f"execute if score @s {OBJ}.{m['id']} matches 1.. run scoreboard players add @s {OBJ} 1"
              for m in MILESTONES]
    show = [
        "# Runs as a player who used /trigger firsts: every milestone and who holds it.",
        f"scoreboard players set @s {TRIGGER} 0",
        f"scoreboard players enable @s {TRIGGER}",
        "# How many this player holds, into their own rf score (only the # holders are the pack's state).",
        *count,
        "tellraw @s " + text("", {"text": "\nServer Firsts", "color": "gold", "bold": True},
                             {"text": "  the first on the server to each, for the season", "color": "gray"}),
    ]
    show += [f"function {NS}:firsts/show/{m['id']}" for m in MILESTONES]
    show.append("tellraw @s " + text(
        "", {"text": "You hold ", "color": "gray"}, {"score": {"name": "@s", "objective": OBJ}, "color": "white"},
        {"text": ". The most firsts at the season's end earns a title.", "color": "gray"}))
    f[f"{FN}/use.mcfunction"] = lines(*show)

    for m in MILESTONES:
        fid = m["id"]
        f[f"{ADVANCEMENT}/{fid}.json"] = json.dumps(advancement(m), indent=2)
        f[f"{FN}/got/{fid}.mcfunction"] = got_function(m)
        f[f"{FN}/claim/{fid}.mcfunction"] = claim_function(m)
        f[f"{FN}/show/{fid}.mcfunction"] = show_function(m)
        note = [f"# {line}" for line in textwrap.wrap(m["reopen"], 106)] if m.get("reopen") else []
        f[f"{FN}/reopen/{fid}.mcfunction"] = lines(
            f"# {m['name']}: nobody holds it any more, and the next to do it claims it. Staff: for a first taken",
            "# by a mistake or an exploit (docs/ADMIN.md, \"Server Firsts\").",
            *note,
            f"data remove storage {STORE} held.{fid}",
            f"scoreboard players reset * {OBJ}.{fid}",
            f"scoreboard players set #{fid} {OBJ} 0",
        )
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- the command line


def season_title(season: int) -> tuple[str, str, str]:
    team, color, prefix = TITLE
    return team.format(season=season), color, prefix.format(season=season)


def title_commands(player: str, season: int) -> list[str]:
    """What staff run once at the season's end (docs/SEASONS.md, "Ending a season")."""
    team, color, prefix = season_title(season)
    return [f"team add {team}", f"team modify {team} color {color}",
            f"team modify {team} prefix {json.dumps(prefix)}", f"team join {team} {mc_string(player)}"]


def show_list(world: Path) -> int:
    firsts = {f.id: f for f in holders(world)}
    for m in MILESTONES:
        f = firsts.get(m["id"])
        week = "" if f is None or f.week is None else f"  week {f.week}"
        print(f"{m['name']:<{NAME_MAX}}  " + (f"{f.player}  (#{f.order}{week})" if f else "open"))
    for f in firsts.values():
        if milestone(f.id) is None:
            print(f"{f.id:<{NAME_MAX}}  {f.player}  (#{f.order}, no longer a milestone)")
    print(f"{len([m for m in MILESTONES if m['id'] in firsts])} of {len(MILESTONES)} claimed")
    return 0


def show_champion(world: Path, season: int) -> int:
    firsts = holders(world)
    best = champion(firsts)
    if best is None:
        print("No firsts claimed: no title this season.")
        return 1
    table = standings(firsts)
    for i, s in enumerate(table[:5], 1):
        print(f"{i}. {s.player}: {s.count} first{'s' if s.count != 1 else ''} (reached at claim #{s.reached})")
    tied = [s.player for s in table if s.count == best.count and s != best]
    if tied:
        print(f"Tied on {best.count} with {', '.join(tied)}: {best.player} reached it first.")
    print(f"\nThe season title goes to {best.player}. Run once, in the console or over RCON:")
    for c in title_commands(best.player, season):
        print(f"  {c}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Server Firsts: who holds each, and the season title.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("list", help="every first and who holds it, from the saved world")
    s.add_argument("world", type=Path, help="the world folder (server/world)")
    c = sub.add_parser("champion", help="who has the most firsts, and the commands for the season title")
    c.add_argument("world", type=Path, help="the world folder (the season's final world)")
    c.add_argument("--season", type=int, required=True, help="the season's number (1 for Season I)")
    args = ap.parse_args(argv)
    if not args.world.is_dir():
        print(f"no world folder at {args.world}")
        return 2
    if args.command == "list":
        return show_list(args.world)
    return show_champion(args.world, args.season)


if __name__ == "__main__":
    sys.exit(main())
