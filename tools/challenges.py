"""Weekly challenges, and the clock the server can't read: which week it is and when the launch weekend ends.

    python tools/challenges.py schedule [--from WEEK] [--weeks 12]   which challenges run in which week
    python tools/challenges.py commands [--at 2026-11-23T08:00:00Z]  the RCON commands that put the server
                                                                     on the clock (deploy/realms-week.sh)

Three challenges a week, one of each kind (solo, faction, explore), from POOL below: the one place to edit
them (docs/ADMIN.md, "Weekly challenges"). Week N runs challenge N mod (how many there are of that kind),
in the order listed. The weeks are tools/season_calendar.py's: week 1 starts on Monday 23 November 2026 at
12 AM Pacific; the launch weekend before it is week 0, and a new week starts every Monday at 12 AM Pacific,
which is Sunday night, after the Saturday event.

Minecraft has no wall clock, so the week number comes from outside: `function realms:challenges/sync
{week:N}` starts week N unless it is already running. The week is a score, so restarts keep it.
deploy/realms-week.sh sends this script's `commands` every hour.

Each challenge done adds 1 to rw.challenges, which unlocks wardrobe skins (tools/wardrobe.py) and carries to
the next season like every rw.* score. This week's progress lives in rc.* scores: cleared every week, never
carried.

How progress is counted, so that it can't be farmed:
  blocks mined   the mined statistic minus the same block placed (`used`), so placing and breaking again
                 counts nothing. One player can place blocks for another to break, but that only moves
                 progress between them: the total across all players stays what the world itself held.
  mobs defeated  an advancement for killing a listed mob type. Players are never on a list.
  loot           an advancement for generating a structure chest's loot, which happens once per chest.
  visits         a location advancement per kind of structure, checked only while that challenge runs.
  days           a player's first time online in a wardrobe day (they start at midnight UTC) this week.
  events         the events pack's attendance: any event begun this week counts (ev.seen).
Water- or vehicle-driven movement and player kills never count.

The launch weekend (Founder's Circlet, tools/wardrobe.py) runs from Saturday 21 November 2026, 5 PM Pacific,
to the end of Sunday 22 November, Pacific. `function realms:rules/launch` opens it; on the server it then
lasts season_calendar.LAUNCH_SECONDS of game time, which stops while the server is empty, so `commands` also sends the
seconds left on the wall clock and the server ends it on time.

Stdlib only, no imports from the other tools, and Python 3.10 or newer, so the VPS runs it straight from the
checkout (deploy/realms-week.sh; the VPS's python3 may be 3.10).
"""
import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

import rcon as server
import season_calendar
from datapacks import NS, lines, text
from events import STATE

FN = f"data/{NS}/function/challenges"
LAUNCHED = "#launched rw.day"   # set when the first launch is done (tools/rules.py reads it)
ADVANCEMENT = f"data/{NS}/advancement/challenges"

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)
FOUNDER_MINUTES = 10   # online this long in the launch weekend earns Founder's Circlet
# What test play before Season I's launch may have earned; the first realms:rules/launch clears it.
TEST_PLAY = ("rw.challenges", "rw.challenges.seen", "rw.launch", "rw.launch.seen", "rw.launchtime")

SOLO, FACTION, EXPLORE = "solo", "faction", "explore"
KINDS = {SOLO: "Solo", FACTION: "Faction", EXPLORE: "Explore"}
NAME_MAX = 30   # a challenge's name, so its menu line fits one line of chat

LOGS = ["oak_log", "spruce_log", "birch_log", "jungle_log", "acacia_log", "dark_oak_log", "mangrove_log",
        "cherry_log", "pale_oak_log", "crimson_stem", "warped_stem"]
# Hostile mobs; the last three are newer, so the tag doesn't fail if this Minecraft lacks them.
HOSTILE = ["zombie", "husk", "drowned", "zombie_villager", "skeleton", "stray", "bogged", "wither_skeleton",
           "creeper", "spider", "cave_spider", "witch", "slime", "magma_cube", "phantom", "pillager",
           "vindicator", "evoker", "ravager", "vex", "guardian", "elder_guardian", "blaze", "ghast", "hoglin",
           "zoglin", "piglin_brute", "silverfish", "endermite", "shulker", "breeze", "warden"]
HOSTILE_OPTIONAL = ["parched", "camel_husk", "zombie_nautilus"]
# Structure loot chests and barrels. Not the bonus chest, and not dispensers.
LOOT_TABLES = [
    "abandoned_mineshaft", "ancient_city", "ancient_city_ice_box", "bastion_bridge", "bastion_hoglin_stable",
    "bastion_other", "bastion_treasure", "buried_treasure", "desert_pyramid", "end_city_treasure", "igloo_chest",
    "jungle_temple", "nether_bridge", "pillager_outpost", "ruined_portal", "shipwreck_map", "shipwreck_supply",
    "shipwreck_treasure", "simple_dungeon", "stronghold_corridor", "stronghold_crossing", "stronghold_library",
    "underwater_ruin_big", "underwater_ruin_small", "woodland_mansion",
    *(f"trial_chambers/{t}" for t in ("corridor", "entrance", "intersection", "intersection_barrel", "supply")),
    *(f"village/village_{t}" for t in (
        "armorer", "butcher", "cartographer", "desert_house", "fisher", "fletcher", "mason", "plains_house",
        "savanna_house", "shepherd", "snowy_house", "taiga_house", "tannery", "temple", "toolsmith", "weaponsmith")),
]
# Kinds of structure for the visit challenges: name -> the structures that count as one.
OVERWORLD = {
    "village": ["village_plains", "village_desert", "village_savanna", "village_snowy", "village_taiga"],
    "outpost": ["pillager_outpost"],
    "ruined_portal": ["ruined_portal", "ruined_portal_desert", "ruined_portal_jungle", "ruined_portal_swamp",
                      "ruined_portal_mountain", "ruined_portal_ocean"],
    "shipwreck": ["shipwreck", "shipwreck_beached"],
    "ocean_ruin": ["ocean_ruin_cold", "ocean_ruin_warm"],
    "mineshaft": ["mineshaft", "mineshaft_mesa"],
    "desert_pyramid": ["desert_pyramid"],
    "jungle_pyramid": ["jungle_pyramid"],
    "swamp_hut": ["swamp_hut"],
    "igloo": ["igloo"],
    "monument": ["monument"],
}

# ---------------------------------------------------------------- the pool: edit here
#
# id     stable and short: it names the challenge's scores (rc.<id>.*), so don't rename one mid-week
# name   what the menu shows (at most NAME_MAX characters); goal: the number to reach
# about  the hover text: what counts
# One way of counting each:
#   mine=[blocks]      mined, minus the same blocks placed
#   stat=[stats]       minecraft.custom statistics that only go up by playing
#   kill=[mobs]        mobs killed by the player
#   loot=True          structure loot chests opened first
#   visit={kind: [structures]}   kinds of structure set foot in
#   days=True          different wardrobe days online
#   event=True         any event attended this week
# Week N runs the (N mod count)th of each kind, so the order is the rotation. Week 0, the launch weekend,
# runs the first of each.
POOL = [
    dict(id="logs", kind=SOLO, name="Chop 128 logs", goal=128, mine=LOGS,
         about="Any log or Nether stem. Logs you placed yourself don't count."),
    dict(id="days", kind=SOLO, name="Play on 3 different days", goal=3, days=True,
         about="Be online on 3 days this week. A new day starts at midnight UTC."),
    dict(id="iron", kind=SOLO, name="Mine 48 iron ore", goal=48, mine=["iron_ore", "deepslate_iron_ore"],
         about="Iron ore or deepslate iron ore. Ore you placed yourself doesn't count."),
    dict(id="hostiles", kind=SOLO, name="Defeat 40 hostile mobs", goal=40, kill=HOSTILE,
         about="Zombies, skeletons, creepers, spiders and the rest. Never players."),
    dict(id="fish", kind=SOLO, name="Catch 20 fish", goal=20, stat=["fish_caught"],
         about="Anything you reel in with a fishing rod counts."),
    dict(id="diamonds", kind=SOLO, name="Mine 6 diamond ore", goal=6, mine=["diamond_ore", "deepslate_diamond_ore"],
         about="Diamond ore or deepslate diamond ore. Ore you placed yourself doesn't count."),
    dict(id="breed", kind=SOLO, name="Breed 16 animals", goal=16, stat=["animals_bred"],
         about="Feed two animals of a kind so they have a baby."),
    dict(id="trade", kind=SOLO, name="Make 20 villager trades", goal=20, stat=["traded_with_villager"],
         about="Every trade with a villager or a wandering trader counts."),
    dict(id="enchant", kind=SOLO, name="Enchant 5 items", goal=5, stat=["enchant_item"],
         about="At an enchanting table."),
    dict(id="debris", kind=SOLO, name="Mine 4 ancient debris", goal=4, mine=["ancient_debris"],
         about="In the Nether. Debris you placed yourself doesn't count."),
    dict(id="event", kind=FACTION, name="Come to an event", goal=1, event=True,
         about="Turn up to any server event this week (Saturdays, 6 PM Pacific)."),
    dict(id="raid", kind=FACTION, name="Win a village raid", goal=1, stat=["raid_win"],
         about="Everyone who helps defend the village counts."),
    dict(id="fortress", kind=FACTION, name="Defeat 15 fortress mobs", goal=15, kill=["blaze", "wither_skeleton"],
         about="Blazes or wither skeletons, in a Nether fortress."),
    dict(id="breezes", kind=FACTION, name="Defeat 6 breezes", goal=6, kill=["breeze"],
         about="The wind mobs of the trial chambers."),
    dict(id="brutes", kind=FACTION, name="Defeat 2 piglin brutes", goal=2, kill=["piglin_brute"],
         about="The axe-carrying piglins that guard bastions."),
    dict(id="loot", kind=EXPLORE, name="Open 8 loot chests", goal=8, loot=True,
         about="Chests and barrels in structures that nobody has opened before you."),
    dict(id="structures", kind=EXPLORE, name="Visit 4 kinds of structure", goal=4, visit=OVERWORLD,
         about="Villages, outposts, ruined portals, shipwrecks, ocean ruins, mineshafts, temples, huts, "
               "igloos and monuments."),
    dict(id="nether", kind=EXPLORE, name="Visit a fortress and a bastion", goal=2,
         visit={"fortress": ["fortress"], "bastion": ["bastion_remnant"]},
         about="Set foot in a Nether fortress and in a bastion remnant."),
    dict(id="rare", kind=EXPLORE, name="Visit 2 rare structures", goal=2,
         visit={"trial_chambers": ["trial_chambers"], "trail_ruins": ["trail_ruins"],
                "ancient_city": ["ancient_city"], "mansion": ["mansion"]},
         about="Two of: trial chambers, trail ruins, an ancient city, a woodland mansion."),
]
WAYS = ("mine", "stat", "kill", "loot", "visit", "days", "event")


def of_kind(kind: str) -> list[dict]:
    return [c for c in POOL if c["kind"] == kind]


# ---------------------------------------------------------------- the clock


def picks(week: int) -> dict[str, dict]:
    """The week's three challenges, by kind. The server works out the same with %= (pick.mcfunction)."""
    return {kind: of_kind(kind)[max(week, 0) % len(of_kind(kind))] for kind in KINDS}


def founder_left(when: dt.datetime) -> int:
    """Seconds left in the launch weekend on the wall clock (0 once it is over)."""
    return max(0, math.ceil((season_calendar.LAUNCH_END - when).total_seconds()))


def commands(when: dt.datetime) -> list[str]:
    """What deploy/realms-week.sh sends over RCON. Both are no-ops when nothing changed, so it runs hourly."""
    out = [f"function {NS}:challenges/sync {{week:{season_calendar.week_at(when)}}}"]
    if when < season_calendar.LAUNCH_END + dt.timedelta(days=1):   # after that there is no window left to keep in step
        out.append(f"function {NS}:wardrobe/founder/sync {{seconds:{founder_left(when)}}}")
    return out


def send(rcon, when: dt.datetime, log=print) -> int:
    """Sends commands(when). A server that isn't running is skipped: the week is a score in the world, so the
    next hour catches up."""
    return server.send_if_running(rcon, commands(when), log,
                                  skipped="server not running: nothing sent (the next hour catches up)")


# ---------------------------------------------------------------- scores


def counters(c: dict) -> list[tuple[str, str, int]]:
    """The challenge's raw scores, as (objective, criterion, sign): progress is the signed sum."""
    cid = c["id"]
    if "mine" in c:
        return ([(f"rc.{cid}.{i}", f"minecraft.mined:minecraft.{b}", 1) for i, b in enumerate(c["mine"])]
                + [(f"rc.{cid}.m{i}", f"minecraft.used:minecraft.{b}", -1) for i, b in enumerate(c["mine"])])
    if "stat" in c:
        return [(f"rc.{cid}.{i}", f"minecraft.custom:minecraft.{s}", 1) for i, s in enumerate(c["stat"])]
    if "kill" in c or "loot" in c:
        return [(f"rc.{cid}.0", "dummy", 1)]
    if "visit" in c:
        return [(f"rc.{cid}.{kind}", "dummy", 1) for kind in c["visit"]]
    return []


def objectives() -> list[tuple[str, str]]:
    """Every objective the challenges use, with its criterion."""
    out = [("challenges", "trigger"), ("rc.week", "dummy"), ("rc.seen", "dummy"), ("rc.days", "dummy"),
           ("rc.lastday", "dummy"), *((f"rc.{k}", "dummy") for k in KINDS)]
    for c in POOL:
        out += [(o, crit) for o, crit, _ in counters(c)] + [(f"rc.{c['id']}.done", "dummy")]
    return out


def weekly() -> list[str]:
    """What a new week clears: every rc.* score but the week itself and who has been greeted for it."""
    return [o for o, crit in objectives() if crit != "trigger" and o not in ("rc.week", "rc.seen")]


# ---------------------------------------------------------------- the data pack


def score(objective: str, color: str = "yellow") -> dict:
    return {"score": {"name": "@s", "objective": objective}, "color": color}


OPEN = {"text": "[Open]", "color": "aqua", "underlined": True,
        "click_event": {"action": "run_command", "command": "/trigger challenges"}}


def progress_function(c: dict) -> str:
    """Runs as each player while the challenge is on: work out rc.<kind>, and finish it at the goal."""
    cid, kind, goal = c["id"], f"rc.{c['kind']}", c["goal"]
    out = [f"# {c['name']}: this week's progress into {kind}, run as each player once a second while it is on."]
    if c.get("days"):
        out.append(f"scoreboard players operation @s {kind} = @s rc.days")
    elif c.get("event"):
        out += [f"scoreboard players set @s {kind} 0",
                f"execute if score @s ev.seen >= #firstevent rc.week run scoreboard players set @s {kind} 1"]
    else:
        out.append(f"scoreboard players set @s {kind} 0")
        for objective, _, sign in counters(c):
            out.append(f"scoreboard players operation @s {kind} {'+=' if sign > 0 else '-='} @s {objective}")
        if any(sign < 0 for _, _, sign in counters(c)):
            out.append(f"execute if score @s {kind} matches ..-1 run scoreboard players set @s {kind} 0")
    out.append(f"execute if score @s {kind} matches {goal}.. unless score @s rc.{cid}.done matches 1 run "
               f"function {NS}:challenges/done/{cid}")
    return lines(*out)


def datapack_files() -> dict[str, str]:
    """The challenges' part of the realms-wardrobe data pack (tools/wardrobe.py writes them together)."""
    f: dict[str, str] = {}
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/challenges.py (the wardrobe's load runs it). Scores are kept across restarts.",
        *(f"scoreboard objectives add {o} {crit}" for o, crit in objectives()),
        "# -1: this world hasn't been told the week yet. The first sync sets it without clearing anything.",
        "execute unless score #week rc.week matches -2147483648.. run scoreboard players set #week rc.week -1",
        "execute unless score #firstevent rc.week matches -2147483648.. run "
        "scoreboard players set #firstevent rc.week 1",
        f"function {NS}:challenges/pick",
    )
    pick = ["# This week's three: challenge (#week mod how many) of each kind, the same as tools/challenges.py picks."]
    for kind in KINDS:
        pick += [f"scoreboard players operation #{kind} rc.week = #week rc.week",
                 f"execute if score #{kind} rc.week matches ..-1 run scoreboard players set #{kind} rc.week 0",
                 f"scoreboard players set #count rc.week {len(of_kind(kind))}",
                 f"scoreboard players operation #{kind} rc.week %= #count rc.week"]
    f[f"{FN}/pick.mcfunction"] = lines(*pick)
    f[f"{FN}/sync.mcfunction"] = lines(
        "# Macro {week:N}: deploy/realms-week.sh runs it every hour (staff can too: docs/ADMIN.md). Starts week N",
        "# unless it is already running: clears last week's progress (not in a world that had no week yet),",
        "# then picks the three.",
        "$execute if score #week rc.week matches $(week) run return 0",
        f"execute unless score #week rc.week matches -1 run function {NS}:challenges/restart",
        "$scoreboard players set #week rc.week $(week)",
        f"function {NS}:challenges/pick",
    )
    f[f"{FN}/restart.mcfunction"] = lines(
        "# Clears everyone's progress this week, offline players too (a new week, or the launch:",
        "# realms:rules/launch). Completed challenges stay counted in rw.challenges.",
        *(f"scoreboard players reset * {o}" for o in weekly()),
        "# Events begun from now on count for the event challenge.",
        f"scoreboard players operation #firstevent rc.week = #event {STATE}",
        "scoreboard players add #firstevent rc.week 1",
    )
    f[f"{FN}/launch.mcfunction"] = lines(
        "# Run by realms:rules/launch: this week's progress starts from zero. At Season I's first launch, what test",
        "# play earned goes too: challenges done, and Founder's Circlet from a window staff opened to try it.",
        "# #launched makes that once only, so a launch run again by mistake wipes nothing earned since; later",
        "# seasons keep the counts they carried.",
        f"function {NS}:challenges/restart",
        *(f"execute if score #season rw.day matches 1 unless score {LAUNCHED} matches 1 run "
          f"scoreboard players reset * {o}" for o in TEST_PLAY),
        f"scoreboard players set {LAUNCHED} 1",
    )
    active = []
    for kind in KINDS:
        for i, c in enumerate(of_kind(kind)):
            active.append(f"execute if score #{kind} rc.week matches {i} as @a run "
                          f"function {NS}:challenges/progress/{c['id']}")
    f[f"{FN}/second.mcfunction"] = lines(
        "# Once a second, from the wardrobe's: the trigger, days this week, a weekly hello, and progress on the",
        "# three challenges that are on.",
        "scoreboard players enable @a challenges",
        f"execute as @a unless score @s rc.lastday = #today rw.day run function {NS}:challenges/day",
        f"execute as @a unless score @s rc.seen = #week rc.week run function {NS}:challenges/greet",
        *active,
    )
    f[f"{FN}/day.mcfunction"] = lines(
        "# This player's first time online in a wardrobe day, this week.",
        "scoreboard players add @s rc.days 1",
        "scoreboard players operation @s rc.lastday = #today rw.day",
    )
    f[f"{FN}/greet.mcfunction"] = lines(
        "# This player's first time online this week (or the week just turned): show them the three.",
        "scoreboard players operation @s rc.seen = #week rc.week",
        "tellraw @s " + text("", {"text": "Weekly challenges", "color": "gold"},
                             {"text": "  new every Monday (Pacific)  ", "color": "gray"}, OPEN),
        f"function {NS}:challenges/lines",
    )
    f[f"{FN}/use.mcfunction"] = lines(
        "# Runs as a player who just used /trigger challenges: the wardrobe's challenges page.",
        f"function {NS}:wardrobe/menu_challenges",
        "scoreboard players set @s challenges 0",
        "scoreboard players enable @s challenges",
    )
    show = ["# One chat line per challenge that is on, with this player's progress (the menu and the hello)."]
    for kind in KINDS:
        for i, c in enumerate(of_kind(kind)):
            show.append(f"execute if score #{kind} rc.week matches {i} run function {NS}:challenges/line/{c['id']}")
    f[f"{FN}/lines.mcfunction"] = lines(*show)

    for c in POOL:
        cid, kind = c["id"], c["kind"]
        hover = {"action": "show_text", "value": c["about"]}
        f[f"{FN}/progress/{cid}.mcfunction"] = progress_function(c)
        f[f"{FN}/line/{cid}.mcfunction"] = lines(
            f"execute if score @s rc.{cid}.done matches 1 run tellraw @s " + text(
                " ", {"text": f"{KINDS[kind]}  ", "color": "gray"},
                {"text": c["name"], "color": "green", "hover_event": hover}, {"text": "  done", "color": "green"}),
            f"execute unless score @s rc.{cid}.done matches 1 run tellraw @s " + text(
                " ", {"text": f"{KINDS[kind]}  ", "color": "gray"},
                {"text": c["name"], "color": "white", "hover_event": hover}, "  ",
                score(f"rc.{kind}"), {"text": f"/{c['goal']}", "color": "gray"}),
        )
        f[f"{FN}/done/{cid}.mcfunction"] = lines(
            f"# {c['name']}: done for this week. One more toward the challenge skins (rw.challenges).",
            f"scoreboard players set @s rc.{cid}.done 1",
            "scoreboard players add @s rw.challenges 1",
            "playsound minecraft:entity.player.levelup player @s ~ ~ ~ 0.6 1.2",
            "tellraw @s " + text({"text": "Challenge done: ", "color": "gold"}, {"text": c["name"], "color": "yellow"},
                                 {"text": " (", "color": "gold"}, score("rw.challenges"),
                                 {"text": " done in all) ", "color": "gold"}, OPEN),
        )
        if "kill" in c or "loot" in c:
            f[f"{ADVANCEMENT}/{cid}.json"] = json.dumps(advancement(c), indent=2)
            f[f"{FN}/reward/{cid}.mcfunction"] = lines(
                "# The advancement fired: count one, and take it back so the next one fires too.",
                f"scoreboard players add @s rc.{cid}.0 1",
                f"advancement revoke @s only {NS}:challenges/{cid}",
            )
        if "kill" in c:
            f[f"data/{NS}/tags/entity_type/challenges/{cid}.json"] = json.dumps({"values": [
                *(f"minecraft:{m}" for m in c["kill"]),
                *({"id": f"minecraft:{m}", "required": False} for m in (HOSTILE_OPTIONAL if c["kill"] is HOSTILE
                                                                         else []))]}, indent=2)
        for group, structures in c.get("visit", {}).items():
            f[f"{ADVANCEMENT}/{cid}/{group}.json"] = json.dumps(visit_advancement(c, group, structures), indent=2)
            f[f"{FN}/reward/{cid}/{group}.mcfunction"] = lines(
                "# In one of these structures while the challenge is on: this kind counts for this week.",
                f"scoreboard players set @s rc.{cid}.{group} 1",
                f"advancement revoke @s only {NS}:challenges/{cid}/{group}",
            )
    return f


def advancement(c: dict) -> dict:
    """A hidden advancement that counts one kill of a listed mob, or one loot chest, then is taken back.

    26.x conditions name their kind with "type", a criterion's "player"/"entity" is one condition (not a list),
    and entity predicates are components ("minecraft:entity_type"); the pre-26 shapes fail the whole datapack
    load (see tools/rules.py)."""
    if "kill" in c:
        criteria = {"kill": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": {
            "type": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:entity_type": f"#{NS}:challenges/{c['id']}"}}}}}
    else:   # one criterion per loot table, as vanilla's loot_bastion does; any of them counts
        criteria = {t.replace("/", "."): {"trigger": "minecraft:player_generates_container_loot",
                                          "conditions": {"loot_tables": f"minecraft:chests/{t}"}}
                    for t in LOOT_TABLES}
    return {"criteria": criteria, "requirements": [list(criteria)],
            "rewards": {"function": f"{NS}:challenges/reward/{c['id']}"}}


def visit_advancement(c: dict, group: str, structures: list[str]) -> dict:
    """Fires (checked once a second) for a player inside one of the structures, only while the challenge is on
    and only until this kind counted, so it costs nothing the rest of the time."""
    index = of_kind(c["kind"]).index(c)
    player = {"type": "minecraft:all_of", "terms": [
        {"type": "minecraft:int_value_check", "test": {"min": index, "max": index},
         "value": {"type": "minecraft:score", "target": {"type": "minecraft:fixed", "name": f"#{c['kind']}"},
                   "score": "rc.week"}},
        {"type": "minecraft:inverted", "term": {
            "type": "minecraft:entity_scores", "entity": "this", "scores": {f"rc.{c['id']}.{group}": {"min": 1}}}},
        {"type": "minecraft:entity_properties", "entity": "this",
         "predicate": {"minecraft:location": {"structures": [f"minecraft:{s}" for s in structures]}}},
    ]}
    return {"criteria": {"visit": {"trigger": "minecraft:location", "conditions": {"player": player}}},
            "rewards": {"function": f"{NS}:challenges/reward/{c['id']}/{group}"}}


# ---------------------------------------------------------------- the command line


def parse_time(value: str) -> dt.datetime:
    when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def schedule(first: int, weeks: int) -> str:
    out = []
    for week in range(first, first + weeks):
        start = season_calendar.week_start(week)
        label = f"week {week:<3} {'from launch,' if week == 0 else 'from Mon'} {start:%d %b %Y}"
        out.append(f"{label:<28} " + " | ".join(f"{KINDS[k]}: {c['name']}" for k, c in picks(week).items()))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weekly challenges: the rotation, and the commands that set the week.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("schedule", help="which challenges run in the coming weeks")
    s.add_argument("--from", dest="first", type=int, help="the first week to show (default: this week)")
    s.add_argument("--weeks", type=int, default=12)
    for name, about in (("commands", "the RCON commands for now (changes nothing)"),
                        ("send", "sends them to the running server (deploy/realms-week.sh, hourly)")):
        c = sub.add_parser(name, help=about)
        c.add_argument("--at", type=parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        if name == "send":
            c.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")
    args = ap.parse_args(argv)
    now = dt.datetime.now(UTC)
    if args.command == "schedule":
        print(schedule(season_calendar.week_at(now) if args.first is None else args.first, args.weeks))
        return 0
    if args.command == "send":
        return send(server.Docker(args.docker), args.at or now)
    print("\n".join(commands(args.at or now)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
