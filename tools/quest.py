"""The first-week quest: five steps a new player can follow in their first days, and a wardrobe skin at the end.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)

What players see: a player who joins a season after its launch, with no play carried from an earlier season and
at most ENROLL_DAYS days played, gets the quest (docs/RETENTION.md, "The first week"). Chat says so once,
and once a day after that (their first second online in a wardrobe day) while it is unfinished, for their
first REMIND_DAYS days played, with how many steps are done. `/trigger quest` (or the Guide's "Your first week")
shows the steps with a tick or the player's progress and a hover that says what counts. Each step done says so
in chat; all of them unlock the Pathfinder blade (rw.quest, tools/wardrobe.py). Anyone can hide it from the
menu ([Hide]) and bring it back the same way. Veterans never see it: they are marked not taking part the first
second they are seen after the launch, and the menu tells them so.

How each step is counted: each one reads a score something else on the server already keeps, never a poll of
its own (STEPS, "score"):
  guide    rq.guide, which the Guide's right-click sets (an Easy NPC scoreboard action, tools/npcs.py)
  home     a hidden advancement on vanilla's any_block_use trigger for a bed, which fires only while the step
           is open for that player (tools/challenges.py's visit advancements do the same)
  faction  st.faction: tools/diplomacy.py's faction number, written in game by the hourly standings run
  claim    st.claimed: 1 once the player has claimed a chunk, from the same hourly run (tools/standings.py)
  outpost  op.visit: 1 once the player has stood in an outpost's square (tools/outposts.py)
A step, once done, stays done: leaving a faction or giving up land later takes nothing back.

The switch: `#on rq` (1 on, 0 off; QUEST_ON is what a new world starts with). While it is off nobody new is
signed up, no step is checked, nothing is said, and /trigger quest says it is off; turned on again, everyone
carries on where they were. Pre-season and test play never count: nothing runs before the launch
(#launched rw.day), and the first launch of a world clears every rq.* score and the skin from test play
(quest/launch, from monkey:challenges/launch), as it clears the challenges.

It lives in the monkey-wardrobe data pack, as the challenges do: wardrobe's second calls quest/second, its tick
answers the trigger. Stdlib only.
"""
import json

from challenges import LAUNCHED
from datapacks import NS, lines, text

FN = f"data/{NS}/function/quest"
ADVANCEMENT = f"data/{NS}/advancement/quest"
TRIGGER = "quest"
OBJ = "rq"                 # #on: the switch; #n: scratch
STATE = "rq.state"         # per player: unset until seen after the launch; then NOT_IN, ON, DONE or HIDDEN
NOT_IN, ON, DONE, HIDDEN = 0, 1, 2, 3
REMINDED = "rq.day"        # the wardrobe day (#today rw.day) the player was last reminded on
REWARD = "rw.quest"        # 1: the quest is done (the Pathfinder blade); carried into later seasons like every rw.*
QUEST_ON = 1               # the switch in a new world (docs/SEASONS.md, "Switches")
ENROLL_DAYS = 3            # at most this many days played when first seen after the launch: new to the server
REMIND_DAYS = 7            # the daily line stops after this many days played
# /trigger quest values: 1 the menu, 2 hide it, 3 bring it back. Add new ones at the end.
MENU, HIDE, SHOW = 1, 2, 3
WARDROBE_PAGE = 1          # the wardrobe page the Pathfinder blade is on (wardrobe.page(); a test checks)

# ---------------------------------------------------------------- the steps: edit here
#
# id      stable and short: it names the step's score (rq.<id>, unless `score` is the step's own)
# name    the menu line; about: its hover, what counts
# score   (objective, n): the step is done once the player's score in it is n or more. For guide and home the
#         score is the step's own (rq.guide, rq.home): the Guide and the advancement set it; for the others
#         another pack keeps it, and the step copies it into rq.<id> the second it is reached, so it stays done.
# The order is the order a new player meets them: spawn first, then out into the world.
STEPS = [
    dict(id="guide", name="Talk to the Guide at spawn", score=("rq.guide", 1),
         about="Right-click the Guide, the gold name at spawn."),
    dict(id="home", name="Set your spawn at a bed", score=("rq.home", 1),
         about="Right-click a bed: you wake up there after you die. There's no /home on this server, so "
               "your bed is your home."),
    dict(id="faction", name="Join or start a faction", score=("st.faction", 1),
         about="/oparties create to start one, or ask in #smp-forum on the Discord to join one. "
               "Counted within the hour."),
    dict(id="claim", name="Claim a chunk", score=("st.claimed", 1),
         about="Right-click a chunk on the world map (M), or stand in it and type /oclaims claim. "
               "Counted within the hour."),
    dict(id="outpost", name="Visit an outpost", score=("op.visit", 1),
         about="Stand in one of the four outposts' squares. /trigger outposts says where they are."),
]
NAME_MAX = 30              # a step's name, so its menu line fits one line of chat
OWN = {"rq.guide", "rq.home"}   # step scores this pack creates (the others are another pack's)


def done_score(step: dict) -> str:
    """The score that says the step is done for good."""
    objective = step["score"][0]
    return objective if objective in OWN else f"{OBJ}.{step['id']}"


def objectives() -> list[tuple[str, str]]:
    return [(TRIGGER, "trigger"), (OBJ, "dummy"), (STATE, "dummy"), (REMINDED, "dummy"),
            *((done_score(s), "dummy") for s in STEPS)]


# ---------------------------------------------------------------- the data pack


OPEN = {"text": "[Open]", "color": "aqua", "underlined": True,
        "click_event": {"action": "run_command", "command": f"/trigger {TRIGGER}"}}
HIDE_LINK = {"text": "[Hide]", "color": "gray", "click_event": {"action": "run_command",
                                                                "command": f"/trigger {TRIGGER} set {HIDE}"}}
SHOW_LINK = {"text": "[Show it again]", "color": "aqua", "click_event": {
    "action": "run_command", "command": f"/trigger {TRIGGER} set {SHOW}"}}
DONE_COUNT = {"score": {"name": "@s", "objective": OBJ}, "color": "white"}


def home_advancement() -> dict:
    """Any use of a bed while the step is open for the player (signed up, not done). The bed sets the respawn
    point, which no other trigger reports; it fires once and the reward makes the step done, so a player who
    finished it never fires it again."""
    player = {"type": "minecraft:all_of", "terms": [
        {"type": "minecraft:entity_scores", "entity": "this", "scores": {STATE: {"min": ON, "max": ON}}},
        {"type": "minecraft:inverted", "term": {
            "type": "minecraft:entity_scores", "entity": "this", "scores": {"rq.home": {"min": 1}}}},
    ]}
    bed = {"type": "minecraft:location_check", "predicate": {"block": {"blocks": "#minecraft:beds"}}}
    return {"criteria": {"bed": {"trigger": "minecraft:any_block_use",
                                 "conditions": {"player": player, "location": bed}}},
            "rewards": {"function": f"{NS}:quest/reward/home"}}


def datapack_files() -> dict[str, str]:
    """The quest's part of the monkey-wardrobe data pack (tools/wardrobe.py writes them together)."""
    f: dict[str, str] = {}
    launched = f"score {LAUNCHED} matches 1"
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/quest.py (the wardrobe's load runs it). Scores are kept across restarts.",
        *(f"scoreboard objectives add {o} {crit}" for o, crit in objectives()),
        "# The switch: set once in a new world, then whatever staff made it (quest/on, quest/off).",
        f"execute unless score #on {OBJ} matches 0.. run scoreboard players set #on {OBJ} {QUEST_ON}",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        "# Once a second, from the wardrobe's (after its new_day, so rw.days is today's): the trigger, then, while",
        "# the quest is on and the season has launched, sign up whoever is seen for the first time and check the",
        "# open steps of those taking part. Nobody else costs more than the selector.",
        f"scoreboard players enable @a {TRIGGER}",
        f"execute unless score #on {OBJ} matches 1 run return 0",
        f"execute unless {launched} run return 0",
        f"execute as @a unless score @s {STATE} matches -2147483648.. run function {NS}:quest/join",
        f"execute as @a[scores={{{STATE}={ON}}}] run function {NS}:quest/check",
    )
    f[f"{FN}/join.mcfunction"] = lines(
        "# The first second this player is seen after the launch (with the quest on). New to the server: no play",
        f"# carried from an earlier season (rw.playbase) and at most {ENROLL_DAYS} days played. Anyone else is",
        "# marked as not taking part, and never hears of it.",
        f"scoreboard players set @s {STATE} {NOT_IN}",
        "execute if score @s rw.playbase matches 1.. run return 0",
        f"execute unless score @s rw.days matches ..{ENROLL_DAYS} run return 0",
        f"scoreboard players set @s {STATE} {ON}",
        f"scoreboard players operation @s {REMINDED} = #today rw.day",
        f"function {NS}:quest/count",
        "tellraw @s " + text("", {"text": "Your first week: ", "color": "gold"},
                             {"text": f"{len(STEPS)} steps to find your feet, and the Pathfinder blade at the "
                                      "end. ", "color": "yellow"}, OPEN, " ", HIDE_LINK),
    )
    remind = ["# Once a wardrobe day, at this player's first second online that day, for their first "
              f"{REMIND_DAYS} days",
              "# played: one line with how far they are.",
              f"scoreboard players operation @s {REMINDED} = #today rw.day",
              f"execute unless score @s rw.days matches ..{REMIND_DAYS} run return 0",
              "tellraw @s " + text("", {"text": "Your first week: ", "color": "gold"}, DONE_COUNT,
                                   {"text": f"/{len(STEPS)} steps done. ", "color": "gray"}, OPEN, " ", HIDE_LINK)]
    f[f"{FN}/remind.mcfunction"] = lines(*remind)
    check = ["# Runs as a player taking part, once a second: each open step whose score is reached is done."]
    for s in STEPS:
        objective, n = s["score"]
        check.append(f"execute unless score @s {done_score(s)} matches 1.. if score @s {objective} matches {n}.. "
                     f"run function {NS}:quest/step/{s['id']}")
    check.append(f"execute unless score @s {REMINDED} = #today rw.day run function {NS}:quest/remind")
    f[f"{FN}/check.mcfunction"] = lines(*check)
    f[f"{FN}/count.mcfunction"] = lines(
        "# How many steps this player has done, into their own rq score (the menu and the reminder show it).",
        f"scoreboard players set @s {OBJ} 0",
        *(f"execute if score @s {done_score(s)} matches 1.. run scoreboard players add @s {OBJ} 1" for s in STEPS),
    )
    for s in STEPS:
        sid = s["id"]
        step = [f"# {s['name']}: done for good.", f"scoreboard players set @s {done_score(s)} 1",
                f"function {NS}:quest/count",
                f"execute if score @s {OBJ} matches {len(STEPS)}.. run return run function {NS}:quest/finish",
                "playsound minecraft:entity.experience_orb.pickup player @s ~ ~ ~ 0.6 1",
                "tellraw @s " + text({"text": "First week: ", "color": "gold"},
                                     {"text": s["name"], "color": "yellow"}, {"text": " done (", "color": "gold"},
                                     DONE_COUNT, {"text": f"/{len(STEPS)}) ", "color": "gold"}, OPEN)]
        f[f"{FN}/step/{sid}.mcfunction"] = lines(*step)
        f[f"{FN}/line/{sid}.mcfunction"] = lines(
            f"execute if score @s {done_score(s)} matches 1.. run return run tellraw @s " + text(
                " ", {"text": s["name"], "color": "green", "hover_event": {"action": "show_text", "value": s["about"]}},
                {"text": "  done", "color": "green"}),
            "tellraw @s " + text(" ", {"text": s["name"], "color": "white",
                                       "hover_event": {"action": "show_text", "value": s["about"]}},
                                 {"text": "  (hover: how)", "color": "dark_gray"}),
        )
    f[f"{ADVANCEMENT}/home.json"] = json.dumps(home_advancement(), indent=2)
    f[f"{FN}/reward/home.mcfunction"] = lines(
        "# The bed advancement fired: the step's score, which the check picks up within a second. Taken back so a",
        "# world whose quest restarts (a test server) can fire it again; the score keeps it from firing twice.",
        "scoreboard players set @s rq.home 1",
        f"advancement revoke @s only {NS}:quest/home",
    )
    f[f"{FN}/finish.mcfunction"] = lines(
        "# Every step done: the quest is over, and the Pathfinder blade is theirs (the wardrobe announces it).",
        f"scoreboard players set @s {STATE} {DONE}",
        f"scoreboard players set @s {REWARD} 1",
        "playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.8 1",
        "tellraw @s " + text({"text": "Your first week is done. ", "color": "gold"},
                             {"text": "Every step, in your first days. Welcome to Monkey SMP.", "color": "yellow"}),
    )
    f[f"{FN}/use.mcfunction"] = lines(
        f"# Runs as a player who just used /trigger {TRIGGER}: {MENU} the menu, {HIDE} hide it, {SHOW} show it again.",
        f"execute if score @s {TRIGGER} matches {HIDE} if score @s {STATE} matches {ON} run function {NS}:quest/hide",
        f"execute if score @s {TRIGGER} matches {SHOW} if score @s {STATE} matches {HIDDEN} run "
        f"scoreboard players set @s {STATE} {ON}",
        f"execute unless score @s {TRIGGER} matches {HIDE} run function {NS}:quest/menu",
        f"scoreboard players set @s {TRIGGER} 0",
        f"scoreboard players enable @s {TRIGGER}",
    )
    f[f"{FN}/hide.mcfunction"] = lines(
        "# Hidden: no more reminders, and no steps checked. /trigger quest still shows it, with a way back.",
        f"scoreboard players set @s {STATE} {HIDDEN}",
        "tellraw @s " + text({"text": "First-week quest hidden. ", "color": "gray"},
                             {"text": f"/trigger {TRIGGER} brings it back.", "color": "dark_gray"}),
    )
    menu = [
        "# The quest's menu. Only a player taking part (or who hid it, or finished it) sees the steps.",
        "tellraw @s " + text("", {"text": "\nYour first week", "color": "gold", "bold": True},
                             {"text": "  five steps, and a skin at the end", "color": "gray"}),
        f"execute unless score #on {OBJ} matches 1 run return run tellraw @s " + text(
            {"text": " The first-week quest is off for now.", "color": "gray"}),
        f"execute unless {launched} run return run tellraw @s " + text(
            {"text": " It starts when the season launches.", "color": "gray"}),
        f"execute unless score @s {STATE} matches {ON}.. run return run tellraw @s " + text(
            {"text": " It's for players new this season. Your challenges: /trigger challenges", "color": "gray"}),
        f"function {NS}:quest/count",
        *(f"function {NS}:quest/line/{s['id']}" for s in STEPS),
        f"execute if score @s {STATE} matches {DONE} run return run tellraw @s " + text(
            " ", {"text": "Done: the Pathfinder blade is in your wardrobe. ", "color": "green"},
            {"text": "[Wardrobe]", "color": "aqua", "click_event": {
                "action": "run_command", "command": f"/trigger wardrobe set {WARDROBE_PAGE}"}}),
        f"execute if score @s {STATE} matches {HIDDEN} run return run tellraw @s " + text(
            " ", {"text": "Hidden: no reminders. ", "color": "gray"}, SHOW_LINK),
        "tellraw @s " + text(" ", {"text": "Reward: the Pathfinder blade. ", "color": "gray"}, DONE_COUNT,
                             {"text": f"/{len(STEPS)} done  ", "color": "gray"}, HIDE_LINK),
    ]
    f[f"{FN}/menu.mcfunction"] = lines(*menu)
    f[f"{FN}/launch.mcfunction"] = lines(
        "# Run by monkey:challenges/launch, before it sets #launched. At a world's first launch, everything test play",
        "# did goes: who was signed up, every step, the skin. A launch run again later clears nothing.",
        f"execute if {launched} run return 0",
        *(f"scoreboard players reset * {o}" for o, crit in objectives() if crit == "dummy" and o != OBJ),
        "# The skin only in Season I: a later season's world carries what players earned before.",
        f"execute if score #season rw.day matches 1 run scoreboard players reset * {REWARD}",
        f"execute if score #season rw.day matches 1 run scoreboard players reset * {REWARD}.seen",
        f"advancement revoke @a only {NS}:quest/home",
    )
    f[f"{FN}/on.mcfunction"] = lines(
        "# Staff: the quest on. Players carry on where they were; anyone first seen while it was off signs up now",
        "# if they are still new enough.",
        f"scoreboard players set #on {OBJ} 1",
        say({"text": "First-week quest: on.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        "# Staff: the quest off. Nobody signs up, nothing is checked or said; progress is kept.",
        f"scoreboard players set #on {OBJ} 0",
        say({"text": "First-week quest: off.", "color": "yellow"}),
    )
    return f


def say(part: dict) -> str:
    return "tellraw @s " + text(part)
