"""Builds the spawn NPCs: the Guide, who greets new players, and the Town Crier, who announces the week's event.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)

It writes (edit this file, not them):
  package/monkey/datapacks/monkey-npcs/          the two Easy NPC presets and the staff functions that place them
  package/monkey/defaults/config/easy_npc/security.cfg

The NPCs are Easy NPC entities (the easy-npc mods in the manifest). Nothing here spawns them: staff place them
once per world with `/function monkey:npcs/guide/here` (docs/ADMIN.md, "Spawn NPCs"). Each has a fixed UUID,
so placing it again replaces it with the preset's current version instead of adding a second one.

The Guide's buttons open what players already reach with /trigger (challenges, standings, wardrobe) by
setting the trigger score, and the pause menu's Monkey SMP links (tools/rules.py) with `dialog show`. The
Crier picks this week's text by the player's `rc.seen`, which the challenges set to the week number
(tools/challenges.py), so it changes on Monday with the challenges.
"""
import datetime as dt
import re
import uuid
from pathlib import Path

import rules
import season_calendar
from datapacks import NS, lines, mcmeta
from repo import Repo

DATAPACK = "monkey-npcs"
FN = f"data/{NS}/function/npcs"
MODEL = "humanoid"
PRESETS = f"data/{NS}/easy_npc/preset/{MODEL}"
STORE = f"{NS}:npcs"
IGNORE_TAG = "global.ignore"  # data packs that follow the Smithed convention (Random Mob Sizes) leave these alone
EASY_NPC = "7.17.1"    # the Easy NPC version the presets were written and tested against (manifest: easy-npc*)

LINKS_DIALOG = f"{NS}:links"   # the pause menu's Monkey SMP links (tools/rules.py)
TRIGGERS = ("challenges", "standings", "wardrobe")

# Every Easy NPC feature gate (security.cfg's feature.*). All of them need an admin (an op), so a builder in
# creative can't give an NPC commands, scores, trades, presets or a new position. Easy NPC still lets any
# creative player open any NPC's editor: see "Spawn NPCs" in docs/ADMIN.md for what that leaves.
FEATURES = ("DIALOG", "TRADING", "COMMAND_ACTION", "SCOREBOARD_ACTION", "MESSAGE_ACTION", "CUSTOM_ACTION",
            "INTERACT_BLOCK_ACTION", "OPEN_TRADING_ACTION", "OBJECTIVE", "FACTION_MANAGEMENT", "MOVEMENT",
            "POSITION", "COMBAT_ATTRIBUTE", "BASE_ATTRIBUTE", "SOUND", "SPAWN_NPC", "WORLD_PRESET",
            "CUSTOM_PRESET", "LOCAL_PRESET", "DEFAULT_PRESET_IMPORT", "URL_RESOURCE")
SECURITY = {
    # A creative player who isn't an op gets no command level: NPCs they edit can't run commands.
    "creativePlayerCommandLevel": "ALL",
    "npcSpawnRateLimitCreative": "0",
    **{f"feature.{f}": "ADMIN" for f in FEATURES},
}

# ---------------------------------------------------------------- what they say

# The Season I calendar (docs/SEASONS.md, "Season I calendar"): week -> that Saturday's event, in players'
# words. Week N's Saturday is tools/season_calendar.py's; tests check it against SEASONS.md. If an
# event moves, change it here, regenerate, release, and place the Crier again (docs/ADMIN.md, "Spawn NPCs").
EVENTS = {
    1: "Faction Raid I",
    2: "the border breaks, from 2500 to 4000 blocks",
    3: "Dragon Night: the End opens, then 90 minutes of Anarchy",
    4: "Faction Raid II",
    5: "the Netherite age begins, with a small event",
    6: "Arena Glory I, for Midwinter",
    7: "the border breaks again, from 4000 to 6000 blocks",
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

GUIDE_HELLO = "Welcome to Monkey SMP! Right-click me if you're new here."
GUIDE_TEXT = ("Hi @initiator, welcome to Monkey SMP! I can go over the short rules, help you find a faction, "
              "or open this week's challenges, the faction standings and your wardrobe.")
# The short rules (package/monkey/defaults/codeofconduct/en_us.txt), cut to what a new player needs first.
RULES_TEXT = "<br>".join((
    "The short rules:",
    "- No combat logging, and no teaming in other factions' fights.",
    "- A faction holds at most 4 players. No insiding.",
    "- Nobody griefs a territory without permission.",
    "- Your first 48 hours come with PvP grace. Attacking a player ends it.",
    "- Spawn is a no-PvP zone, and nobody touches it.",
    "- No hacked clients, x-ray, dupes or exploits. Respect people.",
    "",
    "The full rulebook is in #smp-rules on the Discord.",
))
FACTIONS_TEXT = "<br>".join((
    "A faction is up to 4 players who share land, and most start small. Factions that are recruiting post "
    "in #smp-forum on the Discord.",
    "",
    "To start your own: /oparties create, then /oparties member invite and the player's name.",
))
CRIER_HELLO = "Hear ye! An event every Saturday, new challenges every Monday. Right-click me for this week's."
CRIER_OTHER = "<br>".join((
    f"There's an event every Saturday at {TIME}.",
    "",
    EVERY_WEEK,
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
    return "<br>".join((this, "", then, "", EVERY_WEEK))


# ---------------------------------------------------------------- Easy NPC data


class Byte(int):
    pass


class Long(int):
    pass


def npc_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://monkeysmp.lscaturchio.xyz/npc/{name}"))


def close() -> dict:
    return {"Type": "CLOSE_DIALOG"}


def open_dialog(label: str) -> dict:
    return {"Cmd": label, "Type": "OPEN_NAMED_DIALOG"}


def trigger(name: str) -> dict:
    """Sets the player's trigger score, which is what `/trigger <name>` does; the data pack answers next tick."""
    assert name in TRIGGERS, name
    return {"Cmd": f"set:{name}:1", "Type": "SCOREBOARD"}


def links() -> dict:
    """Shows the pause menu's Monkey SMP links (the Discord first). Run by the NPC, not the player."""
    return {"Cmd": f"/dialog show @initiator {LINKS_DIALOG}", "PermLevel": 2, "Type": "COMMAND"}


def button(label: str, name: str, *actions: dict) -> dict:
    return {"Actions": list(actions), "Label": label, "Name": name}


def dialog(label: str, name: str, text: str, buttons: list[dict], priority: int,
           conditions: list[dict] | None = None) -> dict:
    """priority -1: only opened by a button. Otherwise the highest priority whose conditions all pass opens."""
    # Button labels are prefixed with the dialog's, so each one is unique in the NPC.
    d = {"Buttons": [{**b, "Label": f"{label}_{b['Label']}"} for b in buttons]}
    if conditions:
        d["Conditions"] = conditions
    d.update({"Label": label, "Name": name, "Priority": priority, "Texts": [{"Text": text}]})
    return d


def bubble(text: str) -> dict:
    """A speech bubble over the NPC's head (Easy NPC message target 4), not a chat line."""
    return {"Msg": {"T": Byte(4), "Texts": [text]}, "Type": "MESSAGE"}


CHALLENGES_BUTTON = ("challenges", "This week's challenges", close(), trigger("challenges"))


def guide() -> dict:
    back = button("back", "Back", open_dialog("default"))
    return {
        "events": {"ON_DISTANCE_CLOSE": [bubble(GUIDE_HELLO)], "ON_INTERACTION": [{"Type": "OPEN_DEFAULT_DIALOG"}]},
        "dialogs": [
            dialog("default", "Welcome", GUIDE_TEXT, [
                button("rules", "The short rules", open_dialog("rules")),
                button("factions", "Find a faction", open_dialog("factions")),
                button(*CHALLENGES_BUTTON),
                button("standings", "Faction standings", close(), trigger("standings")),
                button("wardrobe", "Your wardrobe", close(), trigger("wardrobe")),
            ], 10),
            dialog("rules", "The short rules", RULES_TEXT, [
                button("links", "Discord and links", close(), links()), back], -1),
            dialog("factions", "Find a faction", FACTIONS_TEXT, [
                button("links", "Open the Discord", close(), links()), back], -1),
        ],
    }


def crier() -> dict:
    weeks = [dialog(f"week{w}", f"Week {w}", crier_text(w), [button(*CHALLENGES_BUTTON)], 10,
                    [{"Name": "rc.seen", "Operation": "EQUALS", "Type": "SCOREBOARD", "Value": w}])
             for w in range(LAST_WEEK + 1)]
    return {
        "events": {"ON_INTERACTION": [{"Type": "OPEN_DEFAULT_DIALOG"}], "ON_INTERVAL_LONG": [bubble(CRIER_HELLO)]},
        "dialogs": [*weeks, dialog("other", "Any week", CRIER_OTHER, [button(*CHALLENGES_BUTTON)], 1)],
    }


# name -> (what the name tag says, its color, the humanoid skin, what it does, the preset's behaviour)
NPCS = {
    "guide": ("Guide", "gold", "NOOR", "Greets new players: the short rules, factions, challenges, standings and "
                                       "the wardrobe.", guide),
    "crier": ("Town Crier", "yellow", "PROFESSOR_01", "Announces this week's Saturday event and the next one.",
              crier),
}


def preset(name: str) -> dict:
    title, color, variant, about, make = NPCS[name]
    npc = make()
    return {
        "PresetMetadata": {
            "author": "Monkey SMP", "category": "Monkey SMP", "created": Long(1), "description": about,
            "entityTypeId": f"easy_npc:{MODEL}", "modified": Long(1), "name": title, "variantType": variant,
            "version": "1.0.0",
        },
        "data": {
            "ActionData": {"ActionEventSet": npc["events"]},
            # A text component, as entities store their names (a JSON string would show as plain white text).
            "CustomName": {"color": color, "text": title},
            "CustomNameVisible": Byte(1),
            "DialogData": {"DialogDataSet": npc["dialogs"], "Type": "CUSTOM"},
            "EasyNPCVersion": 3,
            "Invulnerable": Byte(1),
            "ObjectiveData": {"ObjectiveDataSet": [{"Type": "LOOK_AT_PLAYER"}, {"Type": "LOOK_AT_RESET"}]},
            "PersistenceRequired": Byte(1),
            "SkinData": {"Type": "DEFAULT"},
            "VariantType": variant,
            "id": f"easy_npc:{MODEL}",
        },
    }


KEY = re.compile(r"[A-Za-z0-9_.+-]+")


def snbt_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def snbt(value, indent: str = "") -> str:
    """SNBT laid out like Easy NPC's own exports: one key per line, short lists of plain values inline."""
    inner = indent + "  "
    if isinstance(value, bool):
        raise TypeError("use Byte for booleans")
    if isinstance(value, Byte):
        return f"{int(value)}b"
    if isinstance(value, Long):
        return f"{int(value)}L"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return snbt_string(value)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{inner}{k if KEY.fullmatch(k) else snbt_string(k)}:{snbt(v, inner)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + indent + "}"
    if isinstance(value, list):
        if not any(isinstance(v, (dict, list)) for v in value):
            return "[" + ",".join(snbt(v, inner) for v in value) + "]"
        return "[\n" + ",\n".join(inner + snbt(v, inner) for v in value) + "\n" + indent + "]"
    raise TypeError(type(value))


def preset_id(name: str) -> str:
    """The identifier `/easy_npc preset import data` takes for a preset in this pack."""
    return f"{NS}:easy_npc/preset/{MODEL}/{name}.npc.snbt"


# ---------------------------------------------------------------- the data pack


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP spawn NPCs: the Guide and the Town Crier (generated by tools/npcs.py)")
    f[f"{FN}/spot.mcfunction"] = lines(
        "# Macro {name:guide}, run as a marker by here.mcfunction: places that NPC where the marker stands. The",
        "# marker, not the admin, places it, so the NPC has no owner.",
        *(f"execute store result storage {STORE} place.{axis} double 0.01 run data get entity @s Pos[{i}] 100"
          for i, axis in enumerate("xyz")),
        f"$function {NS}:npcs/$(name)/place with storage {STORE} place",
        "kill @s[type=minecraft:marker]",
    )
    for name, (title, *_rest) in NPCS.items():
        f[f"{PRESETS}/{name}.npc.snbt"] = snbt(preset(name)) + "\n"
        npc = npc_uuid(name)
        fn = f"{FN}/{name}"
        f[f"{fn}/here.mcfunction"] = lines(
            f"# Run in game by an admin standing where the {title} goes, facing the way it should face: it stands",
            "# in the middle of that block. It has no owner, so only admins and creative players can edit it.",
            "execute unless entity @s[type=minecraft:player] run return run say "
            f"Run this in game, or use /function {NS}:npcs/{name}/place {{x:0.5,y:64,z:0.5,yaw:0}} from here.",
            f"data modify storage {STORE} place.name set value \"{name}\"",
            f"execute store result storage {STORE} place.yaw float 1 run data get entity @s Rotation[0]",
            f"execute align xz positioned ~0.5 ~ ~0.5 summon minecraft:marker run function {NS}:npcs/spot "
            f"with storage {STORE} place",
        )
        f[f"{fn}/place.mcfunction"] = lines(
            f"# Macro {{x:0.5,y:72,z:3.5,yaw:180}}: puts the {title} there, facing yaw (0 south, 90 west, 180 north,",
            "# 270 east). From the server console or RCON, with someone standing near the spot so it is loaded.",
            f"# Its UUID is fixed, so running this again replaces the {title} with the preset's current version",
            "# (removing it first: an import onto the same UUID would keep an owner or edits the preset doesn't set).",
            f"easy_npc delete {npc}",
            f"$easy_npc preset import data {preset_id(name)} $(x) $(y) $(z) {npc}",
            # Turns the entity. (`easy_npc rotate` turns the model on top of it, so the NPC would look at players
            # over its shoulder.)
            f"$rotate {npc} $(yaw) 0",
            # Random Mob Sizes resizes every new mob with a brain once a second; this tag (the Smithed
            # convention it honours) keeps the NPC at its normal size.
            f"tag {npc} add {IGNORE_TAG}",
        )
        f[f"{fn}/remove.mcfunction"] = lines(
            f"# Removes the {title}. Run near it (its chunk has to be loaded).",
            f"easy_npc delete {npc}",
        )
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def security_cfg() -> str:
    head = [
        "# Easy NPC security settings for Monkey SMP (generated by tools/npcs.py; docs/ADMIN.md, \"Spawn NPCs\").",
        "# Copied only when the server has none. Easy NPC adds its other settings and its own notes on first start.",
    ]
    return "\n".join([*head, *(f"{k}={v}" for k, v in SECURITY.items())]) + "\n"


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


def files(repo: Repo) -> dict[Path, str]:
    """Easy NPC's security settings, a default the installer copies once (not part of the pack)."""
    return {repo.defaults / "config" / "easy_npc" / "security.cfg": security_cfg()}
