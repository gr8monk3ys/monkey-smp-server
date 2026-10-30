"""Siege windows: twice a week, at fixed hours, faction claims can be raided (docs/SEASONS.md, "Siege windows").

    python tools/sieges.py windows [--at TIME]    the window open now or next, and the ones after it (changes nothing)
    python tools/sieges.py commands [--at TIME]   the RCON command for now (deploy/monkey-sieges.sh)
    python tools/sieges.py send --docker DIR      sends it to the running server (the timer, every 5 minutes)
    python tools/datapacks.py                     regenerates the monkey-sieges data pack (with the others)

Off until staff switch it on in game (`function monkey:sieges/staff/on`): the pack ships with `#on sg` at 0, and
then claims are protected all the time, as before. Switched on and after the launch, each window in WINDOWS
(Pacific) opens the claims for LENGTH: chat warns WARN_SECONDS before, and says when it opens and closes; the
Discord post is tools/news.py's (the news feed's webhook).

What a window opens is what Open Parties and Claims can change while the server runs, tried on a test server
(docs/SEASONS.md says what was seen): its default player config, for the three options in SETTINGS, which are not
player-configurable on this server (not in playerConfigurablePlayerConfigOptions), so the default is every
player claim's value. `opac default-player-config set ...` works from a data pack function, takes effect at once,
and doesn't touch the server's own claims (spawn) or the wilderness, which have their own configs. Entities (farm
animals, item frames, villagers) stay protected: their options are player-configurable, so a player's own
setting would win anyway. Open Parties and Claims can't open claims for one faction's enemies only, so a window
opens every claim to every player outside its party.

Minecraft can't see the wall clock, so the timer sends it: `function monkey:sieges/clock {now, open, close,
label}`: the minute (Unix time / 60), the seconds until the window open now or next opens (0: open now) and until
it closes, and its hours in words. The pack counts down each second between runs, so the warnings and the open
and close land on the second; each run sets the count right again. The clock (`#now sg`, the minute) is also what
tools/diplomacy.py's 7-day wars end by. A restart keeps the scores: an open window opens the claims again as the
pack loads (Open Parties and Claims may not have saved the change), and the countdowns wait for the next run, so
a window that ended while the server was down closes within 5 minutes of the start.

Stdlib only plus tools/season_calendar.py and tools/rcon.py, and Python 3.10 or newer: the VPS runs it straight
from the checkout.
"""
import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import rcon as server
import season_calendar
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, say, text
from repo import Repo

DATAPACK = "monkey-sieges"
FN = f"data/{NS}/function/sieges"
STORE = f"{NS}:sieges"
OBJ = "sg"
TRIGGER = "sieges"
NOW = f"#now {OBJ}"        # the wall clock in game: the minute (Unix time // 60) the last timer run sent, kept going

# ---------------------------------------------------------------- when: edit here

# (weekday, hour, minute) a window opens, Pacific; weekday 0 is Monday. Wednesday evening and Sunday afternoon:
# clear of Saturday's 6 PM event and of Sunday's 7 PM standings close.
WINDOWS = ((2, 19, 0), (6, 15, 0))
LENGTH = dt.timedelta(hours=2)
WARN_SECONDS = (30 * 60, 5 * 60)   # chat warns this long before a window opens
SLOT_MINUTES = 5                   # how often deploy/monkey-sieges.timer sends the clock

# What a window changes: Open Parties and Claims' default player config, (option, open, closed). The closed
# values are the mod's own defaults, which this server runs; staff who change one by hand change it here too.
SETTINGS = (
    ("claims.protection.exceptions.blocksByPlayers", "E", "N"),         # break and use blocks (doors, chests)
    ("claims.protection.exceptions.blocksByExplosions", "true", "false"),   # TNT and creepers break blocks
    ("claims.protection.exceptions.itemUse", "E", "N"),                 # place blocks (TNT), use items
)
OPAC = "opac default-player-config set"

HELP = [
    ("staff/on", "siege windows on (off by default)"),
    ("staff/off", "siege windows off; an open one closes now"),
    ("staff/status", "on or off, open or not, the next window"),
]


# ---------------------------------------------------------------- the windows


def window_starts(around: dt.datetime, days: int = 8) -> list[dt.datetime]:
    """Every window start from a day before `around` to `days` after, in order (aware, Pacific)."""
    local = around.astimezone(season_calendar.PACIFIC).date()
    out = []
    for i in range(-1, days + 1):
        day = local + dt.timedelta(days=i)
        for weekday, hour, minute in WINDOWS:
            if day.weekday() == weekday:
                out.append(dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=season_calendar.PACIFIC))
    return sorted(out)


def window(when: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """The window open at `when`, else the next one: (opens, closes)."""
    for start in window_starts(when):
        if when < start + LENGTH:
            return start, start + LENGTH
    raise ValueError("no siege window in the next week: WINDOWS is empty")


def recent(when: dt.datetime, within: dt.timedelta) -> list[tuple[dt.datetime, dt.datetime]]:
    """The windows that opened in the `within` before `when` (tools/news.py's posts)."""
    return [(s, s + LENGTH) for s in window_starts(when - within, within.days + 2) if when - within < s <= when]


def label(start: dt.datetime, end: dt.datetime) -> str:
    """'Wednesday 7 to 9 PM Pacific'."""
    a, b = start.astimezone(season_calendar.PACIFIC), end.astimezone(season_calendar.PACIFIC)
    first = season_calendar.clock(a)
    if (a.hour < 12) == (b.hour < 12):
        first = first.removesuffix(" AM").removesuffix(" PM")
    return f"{season_calendar.DAYS[a.weekday()]} {first} to {season_calendar.clock(b)} Pacific"


def commands(when: dt.datetime) -> list[str]:
    """The clock for the pack: always one command, so the minute in game stays right for the wars too."""
    start, end = window(when)
    opens = max(0, math.ceil((start - when).total_seconds()))
    closes = math.ceil((end - when).total_seconds())
    return [f'function {NS}:sieges/clock {{now:{int(when.timestamp() // 60)},open:{opens},close:{closes},'
            f'label:"{label(start, end)}"}}']


# ---------------------------------------------------------------- the data pack


def gray(s: str) -> dict:
    return {"text": s, "color": "gray"}


LABEL = {"nbt": "label", "storage": STORE, "color": "yellow"}


def minutes(holder: str) -> dict:
    return {"score": {"name": holder, "objective": OBJ}, "color": "yellow"}


WHAT = ("Outside your own party, anyone can break blocks, open chests and doors, place blocks and set off TNT in "
        "any faction's claims. Spawn and the wilderness are as always, and so are animals, item frames and "
        "villagers in claims. The other rules still apply.")


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP siege windows (generated by tools/sieges.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:sieges/load")
    hours = int(LENGTH.total_seconds() // 3600)
    warn_long, warn_short = max(WARN_SECONDS), min(WARN_SECONDS)

    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/sieges.py. Scores and storage are kept across restarts.",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard objectives add {TRIGGER} trigger",
        f"scoreboard players set #60 {OBJ} 60",
        "# Off until staff turn it on (staff/on).",
        f"execute unless score #on {OBJ} matches 0.. run scoreboard players set #on {OBJ} 0",
        f"execute unless score #open {OBJ} matches 0.. run scoreboard players set #open {OBJ} 0",
        "# The countdowns are as old as the stop: wait for the timer's next run before acting on them.",
        f"scoreboard players set #synced {OBJ} 0",
        "# A window open when the server stopped opens the claims again (Open Parties and Claims may not have",
        "# saved the change); one that ended meanwhile closes at the timer's next run.",
        f"execute if score #open {OBJ} matches 1 run function {NS}:sieges/unlock",
        f"execute unless score #open {OBJ} matches 1 if score #applied {OBJ} matches 1 run function "
        f"{NS}:sieges/lock",
        f"schedule function {NS}:sieges/second 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:sieges/second 20t replace",
        f"scoreboard players enable @a {TRIGGER}",
        f"execute as @a[scores={{{TRIGGER}=1..}}] run function {NS}:sieges/show",
        "# The clock: a minute every 60 seconds between the timer's runs, which set it right.",
        f"scoreboard players add #sec {OBJ} 1",
        f"execute if score #sec {OBJ} matches 60.. run scoreboard players add {NOW} 1",
        f"execute if score #sec {OBJ} matches 60.. run scoreboard players set #sec {OBJ} 0",
        f"execute if score #opens {OBJ} matches 1.. run scoreboard players remove #opens {OBJ} 1",
        f"execute if score #closes {OBJ} matches 1.. run scoreboard players remove #closes {OBJ} 1",
        f"execute if score #on {OBJ} matches 1 run function {NS}:sieges/check",
    )
    f[f"{FN}/clock.mcfunction"] = lines(
        "# Macro {now, open, close, label} from the timer (tools/sieges.py commands): the minute, the seconds until",
        "# the window open now or next opens (0: open now) and closes, and its hours in words.",
        f"$scoreboard players set {NOW} $(now)",
        f"scoreboard players set #sec {OBJ} 0",
        f"$scoreboard players set #opens {OBJ} $(open)",
        f"$scoreboard players set #closes {OBJ} $(close)",
        f'$data modify storage {STORE} label set value "$(label)"',
        f"scoreboard players set #synced {OBJ} 1",
        f"execute if score #on {OBJ} matches 1 run function {NS}:sieges/check",
    )
    f[f"{FN}/check.mcfunction"] = lines(
        "# Each second while on: open, close or warn, from the countdowns.",
        f"execute unless score #synced {OBJ} matches 1 run return 0",
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        f"execute if score #open {OBJ} matches 1 unless score #closes {OBJ} matches 1.. run return run function "
        f"{NS}:sieges/close",
        f"execute if score #open {OBJ} matches 1 if score #opens {OBJ} matches 1.. run return run function "
        f"{NS}:sieges/close",
        f"execute if score #open {OBJ} matches 1 run return 0",
        f"execute if score #opens {OBJ} matches ..0 if score #closes {OBJ} matches 1.. run return run function "
        f"{NS}:sieges/open",
        f"execute if score #opens {OBJ} matches 1..{warn_short} unless score #w2 {OBJ} matches 1 run return run "
        f"function {NS}:sieges/warn",
        f"execute if score #opens {OBJ} matches 1..{warn_long} unless score #w1 {OBJ} matches 1 run return run "
        f"function {NS}:sieges/warn",
    )
    f[f"{FN}/warn.mcfunction"] = lines(
        f"# {warn_long // 60} and {warn_short // 60} minutes before (or the first second after a restart inside them).",
        f"scoreboard players set #w1 {OBJ} 1",
        f"execute if score #opens {OBJ} matches ..{warn_short} run scoreboard players set #w2 {OBJ} 1",
        f"scoreboard players operation #mins {OBJ} = #opens {OBJ}",
        f"scoreboard players add #mins {OBJ} 59",
        f"scoreboard players operation #mins {OBJ} /= #60 {OBJ}",
        "tellraw @a " + text("", {"text": "Siege window in ", "color": "gold", "bold": True}, minutes("#mins"),
                             {"text": " min", "color": "gold", "bold": True}, gray(" ("), LABEL,
                             gray("). Faction claims can be raided while it is open. /trigger sieges")),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 0.8",
    )
    f[f"{FN}/open.mcfunction"] = lines(
        f"scoreboard players set #open {OBJ} 1",
        "# The minute it opened and closed: tools/news.py's Discord posts read them from the saved world.",
        f"scoreboard players operation #opened {OBJ} = {NOW}",
        f"scoreboard players set #w1 {OBJ} 1",
        f"scoreboard players set #w2 {OBJ} 1",
        f"function {NS}:sieges/unlock",
        "tellraw @a " + text("", {"text": "The siege window is open", "color": "red", "bold": True}, gray(" ("),
                             LABEL, gray(f"). {WHAT}")),
        "title @a times 10 60 20",
        "title @a subtitle " + text({"text": "Claims can be raided until it closes", "color": "gray"}),
        "title @a title " + text({"text": "Siege window open", "color": "red"}),
        "execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1",
    )
    f[f"{FN}/close.mcfunction"] = lines(
        f"scoreboard players set #open {OBJ} 0",
        f"scoreboard players operation #closed {OBJ} = {NOW}",
        f"scoreboard players set #w1 {OBJ} 0",
        f"scoreboard players set #w2 {OBJ} 0",
        f"function {NS}:sieges/lock",
        "tellraw @a " + text("", {"text": "The siege window is closed.", "color": "green", "bold": True},
                             gray(" Claims are protected again. /trigger sieges says when the next one opens.")),
        "execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 1.2",
    )
    f[f"{FN}/unlock.mcfunction"] = lines(
        "# Opens every faction's claims (Open Parties and Claims' default player config; tools/sieges.py SETTINGS).",
        *(f"{OPAC} {key} {opened}" for key, opened, _ in SETTINGS),
        f"scoreboard players set #applied {OBJ} 1",
    )
    f[f"{FN}/lock.mcfunction"] = lines(
        "# Protects the claims again, as the server runs them outside a window.",
        *(f"{OPAC} {key} {closed}" for key, _, closed in SETTINGS),
        f"scoreboard players set #applied {OBJ} 0",
    )

    # ---- /trigger sieges
    f[f"{FN}/show.mcfunction"] = lines(
        "# Runs as a player who used /trigger sieges.",
        f"scoreboard players set @s {TRIGGER} 0",
        f"scoreboard players enable @s {TRIGGER}",
        f"execute unless score #on {OBJ} matches 1 run return run " + say(
            "", {"text": "Siege windows are off: ", "color": "gold"}, gray("claims are protected all the time.")),
        f"execute if score #open {OBJ} matches 1 run scoreboard players operation #mins {OBJ} = #closes {OBJ}",
        f"execute unless score #open {OBJ} matches 1 run scoreboard players operation #mins {OBJ} = #opens {OBJ}",
        f"scoreboard players add #mins {OBJ} 59",
        f"scoreboard players operation #mins {OBJ} /= #60 {OBJ}",
        f"scoreboard players operation #hours {OBJ} = #mins {OBJ}",
        f"scoreboard players operation #hours {OBJ} /= #60 {OBJ}",
        f"scoreboard players operation #mins {OBJ} %= #60 {OBJ}",
        f"execute if score #open {OBJ} matches 1 run tellraw @s " + text(
            "", {"text": "A siege window is open now", "color": "red", "bold": True}, gray(" ("), LABEL, gray("), "),
            minutes("#hours"), gray(" h "), minutes("#mins"), gray(" min left. " + WHAT)),
        f"execute unless score #open {OBJ} matches 1 unless score #synced {OBJ} matches 1 run return run " + say(
            "", {"text": "Siege windows: ", "color": "gold"}, gray("the server is setting its clock; try again "
                                                                "in a few minutes.")),
        f"execute unless score #open {OBJ} matches 1 run tellraw @s " + text(
            "", {"text": "Next siege window: ", "color": "gold"}, LABEL, gray(", in "), minutes("#hours"), gray(" h "),
            minutes("#mins"), gray(f" min, for {hours} hours. " + WHAT)),
    )

    # ---- staff
    f[f"{FN}/staff/on.mcfunction"] = lines(
        f"scoreboard players set #on {OBJ} 1",
        say("", {"text": "Siege windows are on. ", "color": "gold"},
            gray("The next opens on time (the sieges timer must be installed: docs/LIVE.md).")),
        f"function {NS}:sieges/staff/status",
    )
    f[f"{FN}/staff/off.mcfunction"] = lines(
        f"scoreboard players set #on {OBJ} 0",
        f"execute if score #open {OBJ} matches 1 run function {NS}:sieges/close",
        f"execute if score #applied {OBJ} matches 1 run function {NS}:sieges/lock",
        say("", {"text": "Siege windows are off: ", "color": "gold"}, gray("claims are protected all the time.")),
    )
    f[f"{FN}/staff/status.mcfunction"] = lines(
        say("", {"text": "Siege windows: on ", "color": "gold"}, minutes("#on"), gray(", open "), minutes("#open"),
            gray(", claims opened "), minutes("#applied"), gray(", clock set "), minutes("#synced"),
            gray(", seconds to open "), minutes("#opens"), gray(", to close "), minutes("#closes"),
            gray(", window "), LABEL),
    )
    f[f"{FN}/help.mcfunction"] = lines(
        "# Lists the staff commands; click one to put it in the chat box.",
        say("", {"text": "Siege window commands (docs/ADMIN.md):", "color": "gold"}),
        *(say("", {"text": f" {cmd}", "color": "aqua",
               "click_event": {"action": "suggest_command", "command": f"/function {NS}:sieges/{cmd}"}},
              {"text": f"  {note}", "color": "dark_gray"}) for cmd, note in HELP),
    )
    return f


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def show_windows(when: dt.datetime) -> int:
    start, end = window(when)
    local = when.astimezone(season_calendar.PACIFIC)
    print(f"{local:%a %d %b %Y %H:%M} Pacific: " + ("a window is open now" if start <= when else "no window open"))
    for s in [s for s in window_starts(when) if when < s + LENGTH][:4]:
        print(f"  {label(s, s + LENGTH)} ({s:%d %b})")
    return 0


def send(rcon, when: dt.datetime, log=print) -> int:
    """Sends the clock; a server that isn't running is skipped (the next run sends it)."""
    return server.send_if_running(rcon, commands(when), log)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Siege windows: the timer's clock, the windows, the data pack.")
    sub = ap.add_subparsers(dest="command", required=True)
    server.job_subcommands(sub, "sends it to the running server (deploy/monkey-sieges.sh, every 5 minutes)",
                           others=[("windows", "the window open now or next, and the ones after it")])
    args = ap.parse_args(argv)
    if args.command == "windows":
        return show_windows(server.job_time(args))
    return server.run_job(args, commands, send)


if __name__ == "__main__":
    sys.exit(main())
