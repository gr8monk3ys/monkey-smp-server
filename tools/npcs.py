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
opens its dialog. The dialog's buttons run what players already reach with /trigger (challenges, standings,
wardrobe, quest), as the player, and open the pause menu's Monkey SMP links (tools/rules.py). The Crier picks
this week's dialog by the player's `rc.seen`, which the challenges set to the week number (tools/challenges.py),
so it changes on Monday with the challenges.
"""
import datetime as dt
import json
from pathlib import Path

import rules
import season_calendar
import sieges
from datapacks import NS, lines, mcmeta
from repo import Repo

DATAPACK = "monkey-npcs"
FN = f"data/{NS}/function/npcs"
DIALOGS = f"data/{NS}/dialog/npcs"

LINKS_DIALOG = f"{NS}:links"   # the pause menu's Monkey SMP links (tools/rules.py)
TRIGGERS = ("challenges", "standings", "wardrobe", "quest")
GUIDE_STEP = "rq.guide"   # the first-week quest's step that talking to the Guide counts (tools/quest.py)
WEEK = "rc.seen"          # the week number the challenges keep for every online player (tools/challenges.py)

# ---------------------------------------------------------------- what they say

# The Season I calendar (docs/SEASONS.md, "Season I calendar"): week -> that Saturday's event, in players'
# words. Week N's Saturday is tools/season_calendar.py's; tests check it against SEASONS.md. If an event moves,
# change it here, regenerate and release: the Crier says the new text from then on.
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
EVERY_WEEK = ("Every event is in the Discord's events list: press Interested there for a reminder. "
              "New challenges every Monday.")


def siege_hours() -> str:
    """'Wednesday 7 to 9 PM and Sunday 3 to 5 PM Pacific', from tools/sieges.py's WINDOWS."""
    starts = sieges.window_starts(season_calendar.SEASON.launch, 7)
    seen, out = set(), []
    for start in starts:
        if start.weekday() not in seen:
            seen.add(start.weekday())
            out.append((start.weekday(), sieges.label(start, start + sieges.LENGTH).removesuffix(" Pacific")))
    return " and ".join(said for _, said in sorted(out)) + " Pacific"


# The Crier's line on outpost sieges (tools/sieges.py). They can be off, so it says how to check.
SIEGES = (f"Outpost sieges, {siege_hours()}: capture an outpost while one is on for a bonus hour held. "
          "Claims stay protected. /trigger sieges says if one is on.")

# Dialog text: a blank line ("\n\n") starts a new paragraph, "\n" a new line in one.
GUIDE_TEXT = ("Hi, welcome to Monkey SMP! I can go over the short rules, help you find a faction, or open your "
              "first week's steps, this week's challenges, the faction standings and your wardrobe.")
# The short rules (package/monkey/defaults/codeofconduct/en_us.txt), cut to what a new player needs first.
RULES_TEXT = "\n".join((
    "The short rules:",
    "- No combat logging, and no teaming in other factions' fights.",
    f"- A faction holds at most {rules.faction_size()} players. No insiding.",
    "- Nobody griefs a territory without permission.",
    "- Your first 48 hours come with PvP grace. Attacking a player ends it.",
    "- Spawn is a no-PvP zone, and nobody touches it.",
    "- No hacked clients, x-ray, dupes or exploits. Respect people.",
    "",
    f"The full rulebook is on the website: {rules.SITE.removeprefix('https://')}/guide/rules",
))
FACTIONS_TEXT = "\n".join((
    f"A faction is up to {rules.faction_size()} players who share land, and most start small. Factions that are "
    "recruiting post in #smp-forum on the Discord.",
    "",
    "To start your own: /oparties create, then /oparties member invite and the player's name.",
))
CRIER_OTHER = "\n".join((
    f"There's an event every Saturday at {TIME}.",
    "",
    EVERY_WEEK,
    "",
    SIEGES,
))


def day(d: dt.date) -> str:
    return season_calendar.day_words(d)


def crier_text(week: int) -> str:
    season = season_calendar.SEASON
    if week == 0:
        opens = season_calendar.words(season.launch)
        local = season.launch.astimezone(season_calendar.PACIFIC)
        pvp = local + dt.timedelta(seconds=rules.LAUNCH_SECONDS)
        # Judging is the second night at the event hour (docs/SEASONS.md), not a time worked out from the launch.
        this = (f"Season I opens {day(season.saturday(0))} at {opens['pacific']} ({opens['eastern']}): the launch "
                f"hour, then PvP and the Nether open at {season_calendar.clock(pvp)}. The Build Battle wheel spins "
                f"at {season_calendar.clock(local)}, and judging is {day(season.saturday(0) + dt.timedelta(days=1))} "
                "at 6 PM.")
    else:
        this = f"This week: {EVENTS[week]}, {day(season.saturday(week))}, {TIME}."
    if week < LAST_WEEK:
        then = f"Next week: {EVENTS[week + 1]}, {day(season.saturday(week + 1))}."
    else:
        then = f"Season II is planned for {day(season_calendar.SEASON_TWO)}."
    return "\n".join((this, "", then, "", EVERY_WEEK, "", SIEGES))


# ---------------------------------------------------------------- the NPCs in FancyNpcs

# name -> (what the name tag says, its color, what it does). The name is FancyNpcs' NPC name too.
NPCS = {
    "guide": ("Guide", "gold", "Greets new players: the short rules, factions, the first week's steps, challenges, "
                               "standings and the wardrobe."),
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
            button("Find a faction", show(dialog_id("guide/factions"))),
            button("Your first week", trigger("quest")),
            CHALLENGES_BUTTON,
            button("Faction standings", trigger("standings")),
            button("Your wardrobe", trigger("wardrobe")),
        ]),
        "guide/rules": dialog("guide", RULES_TEXT, [button("Discord and links", show(LINKS_DIALOG)), back]),
        "guide/factions": dialog("guide", FACTIONS_TEXT, [button("Open the Discord", show(LINKS_DIALOG)), back]),
    }


def crier_dialogs() -> dict[str, dict]:
    """One dialog per week of the season, and one for anyone without a week."""
    out = {f"crier/week{w}": dialog("crier", crier_text(w), [CHALLENGES_BUTTON], 1) for w in range(LAST_WEEK + 1)}
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
          for w in range(LAST_WEEK + 1)),
        f"dialog show @s {dialog_id('crier/other')}",
    )
    for path, d in dialogs().items():
        f[f"{DIALOGS}/{path}.json"] = json.dumps(d, indent=2, ensure_ascii=False)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}
