"""Builds what the spawn NPCs do: the Guide, who greets new players, and the Town Crier, who announces the week's event.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)

It writes (edit this file, not them):
  package/monkey/datapacks/monkey-npcs/          each NPC's talk function and its dialogs

The NPCs themselves are FancyNpcs NPCs (the fancynpcs plugin). Nothing here makes them: a data pack function
can't be counted on to run a plugin's commands, so staff create each one once with FancyNpcs' own commands
(staff_commands() below, the same lines as docs/ADMIN.md, "Spawn NPCs"; a test keeps the two in step). Each NPC
has one right-click action, a console command, `execute as {player} run function monkey:npcs/<npc>/talk`, and
all it does is in this pack, so a release that changes what they say or do needs nothing from staff.

The Guide's talk function counts the first-week quest's "Talk to the Guide" step (rq.guide, tools/quest.py) and
opens its dialog. The dialog's buttons run what players already reach with /trigger (challenges, wardrobe, which is
now the progress menu, and quest), as the player, and open the pause menu's Monkey SMP links (tools/rules.py). The
Crier picks this week's dialog by the player's `rc.seen`, which the challenges set to the week number
(tools/challenges.py), so it changes on Monday with the challenges.

The NPCs run on the relaunch's Paper server only, so they speak its Season 1 (docs/relaunch/season-1.md and
rules.md): hearts and claims, with no factions, no PvP grace and no launch hour.
"""
import datetime as dt
import json
from pathlib import Path

import rules
import season_calendar
from datapacks import NS, lines, mcmeta
from repo import Repo

DATAPACK = "monkey-npcs"
FN = f"data/{NS}/function/npcs"
DIALOGS = f"data/{NS}/dialog/npcs"

LINKS_DIALOG = f"{NS}:links"   # the pause menu's Monkey SMP links (tools/rules.py)
TRIGGERS = ("challenges", "wardrobe", "quest")
GUIDE_STEP = "rq.guide"   # the first-week quest's step that talking to the Guide counts (tools/quest.py)
WEEK = "rc.seen"          # the week number the challenges keep for every online player (tools/challenges.py)

# ---------------------------------------------------------------- what they say

# The modded Season I's calendar (docs/SEASONS.md, "Season I calendar"): week -> that Saturday's event. The Crier no
# longer says it; the Discord recap (tools/recap.py) and the lore pages (tools/lore.py) read it while
# season_calendar.SEASON is Season I.
EVENTS = {
    1: "Faction Raid I",
    2: "the border breaks, from 5000 to 5500 blocks",
    3: "Dragon Night: the End opens, then 90 minutes of Anarchy",
    4: "Faction Raid II",
    5: "the Netherite age begins, with a small event",
    6: "Arena Glory I, for Midwinter",
    7: "the border breaks again, from 5500 to 6000 blocks",
    8: "Build Battle II",
    9: "Arena Glory II",
    10: "Faction Raid III",
    11: "the finale (the world locks after it)",
    12: "the off-season weekend in the locked world",
}
LAST_WEEK = max(EVENTS)
TIME = "6 PM Pacific (9 PM Eastern)"

# What the Crier says: the relaunch's Season 1 (docs/relaunch/season-1.md, "The calendar"). The tools count it as
# season 2 from week 0, so the doc's week N is week N-1 here. Week -> that Saturday's event, in players' words; the
# border sizes are tools/border.py's ACTS (a test keeps them in step). If an event moves, change it here, regenerate
# and release: the Crier says the new text from then on.
RELAUNCH = 2   # the relaunch's season number (season_calendar.SEASONS, tools/border.py)
CRIER_EVENTS = {
    1: "King of the Hill I",
    2: "the border opens, from 6,000 to 8,000 blocks",
    3: "Revival Night I, then Dragon Night (the End opens at 7 PM)",
    4: "Base of the Week, where staff tour and judge claimed bases",
    5: "the border opens to 10,000 blocks, and the Edgewalker rises at the new edge",
    6: "Revival Night II, then King of the Hill II",
    7: "the Supply Drop, a guarded chest with Crafted Hearts inside",
    8: "the closing: over the week the border closes in from 10,000 to 3,000 blocks",
    9: "the finale (the world locks after it)",
}
CRIER_LAST_WEEK = max(CRIER_EVENTS)   # the finale
START_BORDER = 6000    # the launch border (tools/rules.py's BORDER in the relaunch's rules pack)
STARTING_HEARTS = 10   # LifeStealZ (docs/relaunch/lifesteal.md)
NEWBIE_HOURS = 3       # PvPManager's newbie protection (docs/relaunch/lifesteal.md)
EVERY_WEEK = ("Every event is in the Discord's events list: press Interested there for a reminder. "
              "New challenges every Monday.")

# Dialog text: a blank line ("\n\n") starts a new paragraph, "\n" a new line in one.
GUIDE_TEXT = ("Hi, welcome to Monkey SMP! I can go over the short rules and how hearts and claims work, or open "
              "your first week's steps, this week's challenges and your progress.")
# The short rules (docs/relaunch/rules.md, "The short version").
RULES_TEXT = "\n".join((
    "The short rules:",
    "- Play fair: no cheats, x-ray, dupes or exploits.",
    "- Claimed land can't be griefed or looted. Unclaimed land can.",
    "- PvP is on everywhere except spawn and the market.",
    "- One account per person. No kill trading.",
    "- Be decent in chat. Keep it all-ages.",
    "- Never buy or sell anything from the server for real money.",
    "",
    f"The full rulebook is on the website: {rules.SITE.removeprefix('https://')}/guide/rules",
))
# Hearts and claims (docs/relaunch/lifesteal.md), cut to what a new player needs first.
HEARTS_TEXT = "\n\n".join((
    f"You start with {STARTING_HEARTS} hearts, and 20 is the most. A player kill moves one heart from the victim to "
    "the killer. Dying to anything else costs nothing.",
    "At 0 hearts you're out for 24 hours, then back with 3. A friend can bring you back sooner with a Revive Beacon.",
    "Claim your base with a golden shovel: right-click two corners. Nobody can grief or loot a claim, but you can "
    "still be fought in one. Unclaimed land is fair game.",
    f"Your first {NEWBIE_HOURS} hours come with newbie protection from PvP.",
))


def day(d: dt.date) -> str:
    return season_calendar.day_words(d)


def season() -> season_calendar.Season:
    """The relaunch's calendar, read when called, so a moved season moves what the Crier says."""
    return season_calendar.SEASONS[RELAUNCH]


def ends() -> str:
    """Said from day one, so nobody is surprised by the reset (docs/relaunch/season-1.md)."""
    return f"Season 1 ends with the finale on {day(season().saturday(CRIER_LAST_WEEK))}."


def crier_text(week: int) -> str:
    s = season()
    if week == 0:
        opens = season_calendar.words(s.launch)
        this = (f"Season 1 opens {day(s.saturday(0))} at {opens['pacific']} ({opens['eastern']}). Spawn and the "
                f"market open, the border is {START_BORDER:,} blocks wide, and the End stays closed until Dragon "
                f"Night. Everyone starts with {STARTING_HEARTS} hearts and {NEWBIE_HOURS} hours of newbie "
                f"protection.\n\n{ends()}")
    else:
        this = f"This week: {CRIER_EVENTS[week]}, {day(s.saturday(week))}, {TIME}."
    if week < CRIER_LAST_WEEK:
        then = f"Next week: {CRIER_EVENTS[week + 1]}, {day(s.saturday(week + 1))}."
    else:
        then = f"After the finale comes an off-week, then Season 2 opens {day(s.saturday(week + 1))}."
    return "\n".join((this, "", then, "", EVERY_WEEK))


CRIER_OTHER = "\n".join((
    f"There's an event most Saturdays at {TIME}. {ends()}",
    "",
    EVERY_WEEK,
))


# ---------------------------------------------------------------- the NPCs in FancyNpcs

# name -> (what the name tag says, its color, what it does). The name is FancyNpcs' NPC name too.
NPCS = {
    "guide": ("Guide", "gold", "Greets new players: the short rules, hearts and claims, the first week's steps, "
                               "challenges and your progress."),
    "crier": ("Town Crier", "yellow", "Announces this week's Saturday event and the next one."),
}
CLICK = "RIGHT_CLICK"   # FancyNpcs' trigger for a right-click
SKIN = "<skin>"         # staff's choice: a player name or a skin image's URL (docs/ADMIN.md, "Spawn NPCs")


def talk(name: str) -> str:
    """The function a right-click on that NPC runs, as the player who clicked."""
    return f"{NS}:npcs/{name}/talk"


def console_command(name: str) -> str:
    """The NPC's right-click action. FancyNpcs runs it as the server console and puts the player's name in for
    {player}; the function runs as that player, with the console's permission (so it may use /dialog)."""
    return f"execute as {{player}} run function {talk(name)}"


def staff_commands(name: str) -> list[str]:
    """What staff type in game to make the NPC where they stand, facing their way (docs/ADMIN.md)."""
    title, color, _about = NPCS[name]
    return [
        f"/npc create {name}",
        f"/npc displayname {name} <{color}>{title}</{color}>",
        f"/npc skin {name} {SKIN}",
        f"/npc turn_to_player {name} true",
        f"/npc action {name} {CLICK} add console_command {console_command(name)}",
    ]


# ---------------------------------------------------------------- the dialogs


def run(command: str) -> dict:
    """A dialog button's action: the player runs the command, as if they typed it."""
    return {"type": "minecraft:run_command", "command": command}


def show(dialog: str) -> dict:
    return {"type": "minecraft:show_dialog", "dialog": dialog}


def trigger(name: str) -> dict:
    """What `/trigger <name>` does; every player has these enabled, and the data packs answer next tick."""
    assert name in TRIGGERS, name
    return run(f"/trigger {name}")


def button(label: str, action: dict) -> dict:
    return {"label": label, "width": 150, "action": action}


def dialog_id(path: str) -> str:
    return f"{NS}:npcs/{path}"


def dialog(name: str, text: str, buttons: list[dict], columns: int = 2) -> dict:
    """A dialog headed with the NPC's name: one paragraph of text per blank line, buttons, and Done."""
    title, color, _about = NPCS[name]
    return {
        "type": "minecraft:multi_action",
        "title": {"text": title, "color": color},
        "body": [{"type": "minecraft:plain_message", "width": 300, "contents": paragraph}
                 for paragraph in text.split("\n\n")],
        "columns": columns,
        "actions": buttons,
        "exit_action": {"label": {"translate": "gui.done"}, "width": 150},
    }


CHALLENGES_BUTTON = button("This week's challenges", trigger("challenges"))


def guide_dialogs() -> dict[str, dict]:
    """Dialog path (under monkey:npcs/) -> the dialog. The first is the one a right-click opens."""
    back = button("Back", show(dialog_id("guide")))
    return {
        "guide": dialog("guide", GUIDE_TEXT, [
            button("The short rules", show(dialog_id("guide/rules"))),
            button("Hearts and claims", show(dialog_id("guide/hearts"))),
            button("Your first week", trigger("quest")),
            CHALLENGES_BUTTON,
            button("Your progress", trigger("wardrobe")),
        ]),
        "guide/rules": dialog("guide", RULES_TEXT, [button("Discord and links", show(LINKS_DIALOG)), back]),
        "guide/hearts": dialog("guide", HEARTS_TEXT, [button("Discord and links", show(LINKS_DIALOG)), back]),
    }


def crier_dialogs() -> dict[str, dict]:
    """One dialog per week of the season, and one for anyone without a week."""
    out = {f"crier/week{w}": dialog("crier", crier_text(w), [CHALLENGES_BUTTON], 1) for w in range(CRIER_LAST_WEEK + 1)}
    out["crier/other"] = dialog("crier", CRIER_OTHER, [CHALLENGES_BUTTON], 1)
    return out


def dialogs() -> dict[str, dict]:
    return {**guide_dialogs(), **crier_dialogs()}


# ---------------------------------------------------------------- the data pack


def talk_head(name: str) -> list[str]:
    title = NPCS[name][0]
    return [
        f"# Run by the {title}'s FancyNpcs right-click action, from the server console, as the player who clicked:",
        f"#   {console_command(name)}",
        "# (docs/ADMIN.md, \"Spawn NPCs\"). The console's permission lets it show a dialog.",
        "execute unless entity @s[type=minecraft:player] run return run say Run it as a player: "
        f"execute as <player> run function {talk(name)}",
    ]


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP spawn NPCs: what the Guide and the Town Crier say "
                              "(generated by tools/npcs.py)")
    f[f"{FN}/guide/talk.mcfunction"] = lines(
        *talk_head("guide"),
        "# A step of the first-week quest (tools/quest.py).",
        f"scoreboard players set @s {GUIDE_STEP} 1",
        f"dialog show @s {dialog_id('guide')}",
    )
    f[f"{FN}/crier/talk.mcfunction"] = lines(
        *talk_head("crier"),
        "# This week's, by the challenges' week number; anyone without one gets the general one.",
        *(f"execute if score @s {WEEK} matches {w} run return run dialog show @s {dialog_id(f'crier/week{w}')}"
          for w in range(CRIER_LAST_WEEK + 1)),
        f"dialog show @s {dialog_id('crier/other')}",
    )
    for path, d in dialogs().items():
        f[f"{DIALOGS}/{path}.json"] = json.dumps(d, indent=2, ensure_ascii=False)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}
