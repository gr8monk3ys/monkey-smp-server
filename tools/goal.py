"""The weekly server goal: one target a week that every player's play counts toward together.

    python tools/goal.py schedule [--from WEEK] [--weeks 12]   which goal runs in which week
    python tools/datapacks.py                                  regenerate it with every other generated pack

What players see: a line under this week's challenges (`/trigger challenges`, and the weekly hello) with the goal
and the server's total so far, an announcement to everyone at half way and when it is reached, and at the
target a celebration: a title on everyone's screen, a sound, and fireworks over the standings board at spawn.
Nothing is given (the owners shelved the economy), so there is nothing to farm for. The Sunday recap has a line
for it (recap.server_goal).

The week is the challenges' (tools/challenges.py): a new goal every Monday at 12 AM Pacific, the same moment the
challenges change, picked from POOL by the week number (week N runs POOL[N mod len]), so `schedule` shows what is
coming. The launch weekend is week 0 and runs the first.

How it is counted: vanilla statistic scoreboards, one per thing that counts (rg.<id>.<n>): blocks mined minus
the same blocks placed (as the challenges count them, so placing and breaking again adds nothing), or one
statistic. Every CHECK_SECONDS the online players' counts this period are added to the server's total (#total
rg) and cleared; statistics only move while a player is online, so nothing is lost, and nothing scans offline
players. Creative and spectator players' counts are thrown away (staff building at spawn). The total never goes
below zero.

The switch: `#on rg` (1 on, 0 off; GOAL_ON in a new world). Off, nothing is counted, shown, announced or posted.
Pre-season and test play never count: nothing is counted before the launch (#launched rw.day), and the launch
clears the week (challenges/launch runs challenges/restart, which runs goal/restart).

It lives in the monkey-wardrobe data pack, as the challenges do. Stdlib only, and Python 3.10 or newer.
"""
import argparse
import datetime as dt
import sys

import season_calendar
from challenges import LAUNCHED, LOGS
from datapacks import NS, lines, text

FN = f"data/{NS}/function/goal"
OBJ = "rg"                 # #on, #idx (POOL index this week), #week (the week it was picked for), #target,
                           # #total, #said (0, 50 or 100: the milestones announced), #sec, #pct, #100
STORE = f"{NS}:goal"       # name: this week's goal as players read it; status: "" or " reached"
GOAL_ON = 1                # the switch in a new world (docs/SEASONS.md, "Switches")
CHECK_SECONDS = 5          # how often the online players' counts are added up
HALF = 50
NAME_MAX = 24              # a goal's name, so "Server goal: NAME  12345/12345 reached" fits one line
BOARD = "st.board"         # the standings board at spawn (tools/standings.py): the fireworks go up over it

# ---------------------------------------------------------------- the pool: edit here
#
# id      stable and short: it names the goal's scores (rg.<id>.<n>), so don't rename the one that is on
# name    what players read (at most NAME_MAX characters); target: the server's total to reach
# about   what counts, for the docs and the recap
# One way of counting each:  mine=[blocks] (mined minus placed)  stat=minecraft.custom statistic
# Targets are for about 20 to 30 active players; staff can change this week's (docs/ADMIN.md, "Weekly server
# goal"). The launch weekend (week 0) is 31 hours, so the first is one everyone does anyway.
POOL = [
    dict(id="logs", name="Chop logs", target=4000, mine=LOGS,
         about="Any log or Nether stem, minus logs placed."),
    dict(id="mobs", name="Defeat mobs", target=2500, stat="mob_kills",
         about="Any mob killed by a player. Players never count."),
    dict(id="diamonds", name="Mine diamond ore", target=250, mine=["diamond_ore", "deepslate_diamond_ore"],
         about="Diamond ore or deepslate diamond ore, minus ore placed."),
    dict(id="fish", name="Catch fish", target=400, stat="fish_caught",
         about="Anything reeled in with a fishing rod."),
    dict(id="trades", name="Trade with villagers", target=1000, stat="traded_with_villager",
         about="Every trade with a villager or a wandering trader."),
    dict(id="breed", name="Breed animals", target=600, stat="animals_bred",
         about="Every baby animal bred."),
    dict(id="debris", name="Mine ancient debris", target=120, mine=["ancient_debris"],
         about="Ancient debris in the Nether, minus debris placed."),
]


def pick(week: int) -> dict:
    """The week's goal. The server works out the same index with %= (pick.mcfunction)."""
    return POOL[max(week, 0) % len(POOL)]


def counters(g: dict) -> list[tuple[str, str, int]]:
    """The goal's statistic objectives, as (objective, criterion, sign): the total is the signed sum."""
    if "mine" in g:
        return ([(f"rg.{g['id']}.{i}", f"minecraft.mined:minecraft.{b}", 1) for i, b in enumerate(g["mine"])]
                + [(f"rg.{g['id']}.m{i}", f"minecraft.used:minecraft.{b}", -1) for i, b in enumerate(g["mine"])])
    return [(f"rg.{g['id']}.0", f"minecraft.custom:minecraft.{g['stat']}", 1)]


def objectives() -> list[tuple[str, str]]:
    return [(OBJ, "dummy"), *((o, crit) for g in POOL for o, crit, _ in counters(g))]


# ---------------------------------------------------------------- the data pack


def total() -> dict:
    return {"score": {"name": "#total", "objective": OBJ}, "color": "white"}


def target() -> dict:
    return {"score": {"name": "#target", "objective": OBJ}, "color": "white"}


def name() -> dict:
    return {"nbt": "name", "storage": STORE, "color": "yellow"}


def fireworks() -> list[str]:
    """Three rockets over each standings board (spawn), high enough that their bursts hurt nobody."""
    item = ('{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":{flight_duration:2b,'
            'explosions:[{shape:"large_ball",colors:[I;16766720,16739125],fade_colors:[I;16777215],'
            'has_trail:1b,has_twinkle:1b}]}}}')
    return [f"execute as @e[type=minecraft:text_display,tag={BOARD}] at @s run summon minecraft:firework_rocket "
            f"~{dx} ~4 ~{dz} {{LifeTime:{life},FireworksItem:{item}}}"
            for dx, dz, life in (("", "", 30), ("2", "", 36), ("-2", "", 42))]


def datapack_files() -> dict[str, str]:
    """The goal's part of the monkey-wardrobe data pack (tools/wardrobe.py writes them together)."""
    f: dict[str, str] = {}
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/goal.py (the wardrobe's load runs it, before challenges/load picks the week).",
        *(f"scoreboard objectives add {o} {crit}" for o, crit in objectives()),
        "# The switch: set once in a new world, then whatever staff made it (goal/on, goal/off).",
        f"execute unless score #on {OBJ} matches 0.. run scoreboard players set #on {OBJ} {GOAL_ON}",
        f"execute unless score #week {OBJ} matches -2147483648.. run scoreboard players set #week {OBJ} -2",
        f"scoreboard players add #total {OBJ} 0",
        f"scoreboard players add #said {OBJ} 0",
        f"scoreboard players set #100 {OBJ} 100",
        f'execute unless data storage {STORE} status run data modify storage {STORE} status set value ""',
    )
    pick = ["# Run by challenges/pick, once the week is known: a new week's goal, its name and target. The same",
            "# week again (every server start) keeps what it has, so a target staff changed stays.",
            f"execute if score #week {OBJ} = #week rc.week run return 0",
            f"scoreboard players operation #week {OBJ} = #week rc.week",
            f"scoreboard players operation #idx {OBJ} = #week rc.week",
            f"execute if score #idx {OBJ} matches ..-1 run scoreboard players set #idx {OBJ} 0",
            f"scoreboard players set #n {OBJ} {len(POOL)}",
            f"scoreboard players operation #idx {OBJ} %= #n {OBJ}"]
    for i, g in enumerate(POOL):
        pick.append(f"execute if score #idx {OBJ} matches {i} run function {NS}:goal/set/{g['id']}")
    f[f"{FN}/pick.mcfunction"] = lines(*pick)
    f[f"{FN}/restart.mcfunction"] = lines(
        "# Run by challenges/restart (a new week, or the launch): the server's count starts from zero.",
        *(f"scoreboard players reset * {o}" for o, crit in objectives() if crit != "dummy"),
        f"scoreboard players set #total {OBJ} 0",
        f"scoreboard players set #said {OBJ} 0",
        f'data modify storage {STORE} status set value ""',
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"# Once a second, from the wardrobe's: every {CHECK_SECONDS} seconds, while the goal is on and the season",
        "# has launched, add up what the online players did and announce a milestone.",
        f"execute unless score #on {OBJ} matches 1 run return 0",
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        f"scoreboard players add #sec {OBJ} 1",
        f"execute if score #sec {OBJ} matches ..{CHECK_SECONDS - 1} run return 0",
        f"scoreboard players set #sec {OBJ} 0",
        *(f"execute if score #idx {OBJ} matches {i} run function {NS}:goal/count/{g['id']}"
          for i, g in enumerate(POOL)),
        f"execute if score #total {OBJ} matches ..-1 run scoreboard players set #total {OBJ} 0",
        f"execute if score #target {OBJ} matches ..0 run scoreboard players set #target {OBJ} 1",
        f"scoreboard players operation #pct {OBJ} = #total {OBJ}",
        f"scoreboard players operation #pct {OBJ} *= #100 {OBJ}",
        f"scoreboard players operation #pct {OBJ} /= #target {OBJ}",
        f"execute if score #pct {OBJ} matches 100.. unless score #said {OBJ} matches 100.. run "
        f"function {NS}:goal/reached",
        f"execute if score #pct {OBJ} matches {HALF}.. unless score #said {OBJ} matches {HALF}.. run "
        f"function {NS}:goal/half",
    )
    for g in POOL:
        gid = g["id"]
        f[f"{FN}/set/{gid}.mcfunction"] = lines(
            f"# {g['name']}: this week's goal.",
            f"scoreboard players set #target {OBJ} {g['target']}",
            f"data modify storage {STORE} name set value {text(g['name'])}",
        )
        count = [f"# {g['name']}: the online players' counts since the last check go into the total, then start "
                 "again.",
                 "# Creative and spectator players' are dropped."]
        for o, _, sign in counters(g):
            count.append(f"scoreboard players operation #total {OBJ} {'+=' if sign > 0 else '-='} "
                         f"@a[gamemode=!creative,gamemode=!spectator] {o}")
        count += [f"scoreboard players reset @a {o}" for o, _, _ in counters(g)]
        f[f"{FN}/count/{gid}.mcfunction"] = lines(*count)
    progress = [name(), {"text": "  ", "color": "gray"}, total(), {"text": "/", "color": "gray"}, target()]
    f[f"{FN}/half.mcfunction"] = lines(
        f"scoreboard players set #said {OBJ} {HALF}",
        "tellraw @a " + text("", {"text": "Server goal half way: ", "color": "gold"}, *progress,
                             {"text": ". Everyone's play counts.", "color": "gray"}),
    )
    f[f"{FN}/reached.mcfunction"] = lines(
        "# The target is reached: a celebration for everyone online, and fireworks over the board at spawn.",
        f"scoreboard players set #said {OBJ} 100",
        f'data modify storage {STORE} status set value " reached"',
        "tellraw @a " + text("", {"text": "Server goal reached! ", "color": "gold", "bold": True}, *progress,
                             {"text": ". Thank you, everyone. Fireworks at spawn.", "color": "gray"}),
        "title @a subtitle " + text(name()),
        "title @a title " + text({"text": "Server goal reached", "color": "gold", "bold": True}),
        "execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1",
        *fireworks(),
    )
    f[f"{FN}/line.mcfunction"] = lines(
        "# This week's goal, one chat line (the challenges page and the weekly hello).",
        f"execute unless score #on {OBJ} matches 1 run return 0",
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        "tellraw @s " + text(" ", {"text": "Server goal  ", "color": "gray"}, *progress,
                             {"nbt": "status", "storage": STORE, "color": "green"}),
    )
    f[f"{FN}/on.mcfunction"] = lines(
        "# Staff: the goal on. Counting starts again from where the total was.",
        f"scoreboard players set #on {OBJ} 1",
        "tellraw @s " + text({"text": "Weekly server goal: on.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        "# Staff: the goal off. Nothing is counted, shown, announced or posted.",
        f"scoreboard players set #on {OBJ} 0",
        "tellraw @s " + text({"text": "Weekly server goal: off.", "color": "yellow"}),
    )
    f[f"{FN}/target.mcfunction"] = lines(
        "# Staff, macro {n:300}: this week's target is n (until the week turns). A milestone already passed is",
        "# not said again; one now passed is said within seconds.",
        f"$scoreboard players set #target {OBJ} $(n)",
        "tellraw @s " + text("", {"text": "This week's server goal target: ", "color": "green"}, target()),
    )
    return f


# ---------------------------------------------------------------- the Sunday recap


def recap_line(scores: dict[str, dict[str, int]], week: int) -> list[str] | None:
    """The recap's line for the goal of `week`, from the saved scoreboard: [] when the goal is off or nothing
    was counted, None when the world's goal is another week's (a close that ran after Monday's turnover)."""
    held = scores.get(OBJ, {})
    if held.get("#on", GOAL_ON) != 1 or "#week" not in held:   # off, or a world without the goal yet
        return []
    if max(held["#week"], 0) != max(week, 0):
        return None
    idx = held.get("#idx", 0)
    if not 0 <= idx < len(POOL):
        return None
    g, done, aim = POOL[idx], max(held.get("#total", 0), 0), max(held.get("#target", POOL[idx]["target"]), 1)
    if done == 0:
        return []
    if held.get("#said", 0) >= 100 or done >= aim:
        return [f"**Server goal:** {g['name']}: reached, {done:,} of {aim:,}. Fireworks at spawn."]
    return [f"**Server goal:** {g['name']}: {done:,} of {aim:,} so far ({done * 100 // aim}%), until Monday "
            "12 AM Pacific."]


# ---------------------------------------------------------------- the command line


def schedule(first: int, weeks: int) -> str:
    out = []
    for week in range(first, first + weeks):
        start = season_calendar.week_start(week)
        label = f"week {week:<3} {'from launch,' if week == 0 else 'from Mon'} {start:%d %b %Y}"
        g = pick(week)
        out.append(f"{label:<28} {g['name']}: {g['target']:,}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The weekly server goal: what runs when.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("schedule", help="which goal runs in the coming weeks")
    s.add_argument("--from", dest="first", type=int, help="the first week to show (default: this week)")
    s.add_argument("--weeks", type=int, default=12)
    args = ap.parse_args(argv)
    first = season_calendar.week_at(dt.datetime.now(season_calendar.UTC)) if args.first is None else args.first
    print(schedule(first, args.weeks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
