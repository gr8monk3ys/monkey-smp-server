"""Builds the monkey-wardrobe data pack: the retention scores (rw.*), the daily job and the progress menu.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)
    python tools/wardrobe.py commands  the RCON command that starts a new day (deploy/monkey-day.sh sends it)

It writes, generated (edit this file, not it):
  package/monkey/datapacks/monkey-wardrobe/       the rw.* scores, the day, /trigger wardrobe, and with them the
                                                  weekly challenges, the weekly server goal and the first-week quest
The pack is still called the wardrobe, as are its trigger and functions, because deploy scripts, other packs and
tools call them by those names. The cosmetic skins it was named for are retired: the relaunch dropped the client
resource pack their models were in, so a skinned item would show a missing model. Cosmetics come from the
UltraCosmetics plugin now (docs/RETENTION.md), and nothing here changes how an item looks.

Retention scores (all per player name, so the store and staff can set them while the player is offline). They
unlock nothing here any more; they are kept because the store, staff, other packs and tools set or read them,
and tools/season.py carries them into the next season:
  rw.days     days played (one per real day the player logs in; never resets, so no streak anxiety)
  rw.hours    hours played (from the play_time statistic, plus rw.playbase: play carried from earlier worlds)
  rw.months   months of access pass bought in total (the store)
  rw.invites  friends invited who bought a pass (the store, Front Desk's /referral)
  rw.tier     supporter tier: 1 Ember, 2 Banner, 3 Crown (0 when it lapses; the store)
  rw.founder  1 for everyone who played during the first season
  rw.s2       1 for everyone who played during Season II (SEASON_MARKS: one mark per season after the first)
  rw.champion 1 for the season champion's roster (staff set it after the finale; never sold)
  rw.kin      1 for both players of a referral: a member's code on a new buyer's Tebex purchase (Front Desk's
              /referral posts the commands or sends them over RCON; never sold, no discount)
  rw.events   events attended (the monkey-events pack counts it, once per event)
  rw.<holiday>  1 for coming to that holiday's event (staff set it at the event; never sold)
  rw.challenges  weekly challenges done, in all seasons together (tools/challenges.py; never sold)
  rw.quest    1 once the first-week quest is done (tools/quest.py)
  rw.launch   1 for being online FOUNDER_MINUTES in Season I's launch weekend (never sold); rw.launchtime
              counts their seconds online while that window is open (`function monkey:wardrobe/founder/...`)
`function monkey:wardrobe/day` starts a new day; deploy/monkey-day.sh starts it at midnight UTC through
`function monkey:wardrobe/day_once {stamp:YYYYMMDD}` (`send`), which a retry the same UTC date leaves alone.
`/trigger wardrobe` (any value) and `/trigger challenges` open the same menu: the counts above, this week's
challenges (tools/challenges.py), the weekly server goal (tools/goal.py) and, for a player taking it, the
first-week quest (tools/quest.py).
Every rw.* score lives in the world's scoreboard, so a new season's world starts without them:
tools/season.py carries them over (docs/SEASONS.md, "Ending a season").
"""
import argparse
import datetime as dt
import os
import sys
from pathlib import Path

import challenges
import goal
import quest
import rcon as server
from challenges import FOUNDER_MINUTES
from datapacks import NS, function_tag, mcmeta, text
from repo import Repo
from season_calendar import LAUNCH_SECONDS

DATAPACK = "monkey-wardrobe"
JOB_PACKS = (DATAPACK,)   # the data packs the day job needs on (deploy/lib.sh skips it while one is off)

# Holidays (docs/SEASONS.md): objective -> (name, when). Staff set it for everyone who comes to the event.
HOLIDAYS = {
    "rw.hallowtide": ("Hallowtide", "late October"),
    "rw.midwinter": ("Midwinter", "late December"),
    "rw.midsummer": ("Midsummer", "late June"),
}
# Seasons after the first: objective -> (season, its numeral). Everyone online while #season is that season gets
# it, as rw.founder in Season I. Add the next season's here.
SEASON_MARKS = {"rw.s2": (2, "II")}
# The season champion's roster (docs/SEASONS.md, "The season champion"): staff set it after the finale.
CHAMPION = "rw.champion"
# A referral (docs/RETENTION.md, "Referrals"): set for the new buyer and the member whose code they used.
KIN = "rw.kin"
# The scores the Tebex store sets (docs/RETENTION.md). Event, holiday, challenge and launch scores must never
# be among them.
SOLD = {"rw.months", "rw.tier"}
# Every per-player retention score the pack keeps (each starts at 0 for everyone online, so selectors find it).
SCORES = ["rw.days", "rw.months", "rw.invites", "rw.tier", "rw.founder", "rw.events", *HOLIDAYS, "rw.playbase",
          "rw.challenges", "rw.launch", *SEASON_MARKS, CHAMPION, quest.REWARD, KIN]
# The counts the menu shows: objective -> what it counts.
COUNTED = {"rw.days": "days played", "rw.hours": "hours played", "rw.events": "events",
           "rw.challenges": "challenges done in all seasons"}

MENU = 1   # /trigger wardrobe: every value opens the menu (old links to 2 to 5 too)


# ---------------------------------------------------------------- the data pack


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    fn = f"data/{NS}/function/wardrobe"
    f["pack.mcmeta"] = mcmeta("Monkey SMP retention scores, weekly challenges and the first-week quest "
                              "(generated by tools/wardrobe.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:wardrobe/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:wardrobe/tick")

    objectives = ["wardrobe trigger", "rw.play minecraft.custom:minecraft.play_time", "rw.hours dummy",
                  "rw.days dummy", "rw.lastday dummy", "rw.months dummy", "rw.invites dummy", "rw.tier dummy",
                  "rw.founder dummy", "rw.day dummy", "rw.const dummy", "rw.events dummy", "rw.playbase dummy",
                  "rw.challenges dummy", "rw.launch dummy", "rw.launchtime dummy", f"{quest.REWARD} dummy",
                  *(f"{o} dummy" for o in HOLIDAYS), *(f"{o} dummy" for o in SEASON_MARKS),
                  f"{CHAMPION} dummy", f"{KIN} dummy"]
    f[f"{fn}/load.mcfunction"] = "\n".join([
        "# Generated by tools/wardrobe.py. Scores are created once and kept across restarts.",
        *(f"scoreboard objectives add {o}" for o in objectives),
        "scoreboard players set #hour rw.const 72000",
        "scoreboard players set #second rw.const 20",
        "scoreboard players add #today rw.day 0",
        "# The first season runs until staff set #season to 2; everyone who plays in it is a founder.",
        "execute unless score #season rw.day matches -2147483648.. run scoreboard players set #season rw.day 1",
        f"function {NS}:quest/load",
        "# Before challenges/load, which picks the week's goal (goal/pick) with its scores.",
        f"function {NS}:goal/load",
        f"function {NS}:challenges/load",
        f"schedule function {NS}:wardrobe/second 20t replace",
    ]) + "\n"
    f[f"{fn}/tick.mcfunction"] = (f"execute as @a[scores={{wardrobe=1..}}] run function {NS}:wardrobe/use\n"
                                  f"execute as @a[scores={{challenges=1..}}] run function {NS}:challenges/use\n"
                                  f"execute as @a[scores={{{quest.TRIGGER}=1..}}] run function {NS}:quest/use\n")
    f[f"{fn}/second.mcfunction"] = "\n".join([
        "# Once a second: let everyone use the trigger, count days and hours, mark founders, keep the launch",
        "# weekend's window, the weekly challenges, the first-week quest and the server goal going.",
        "scoreboard players enable @a wardrobe",
        *(f"scoreboard players add @a {o} 0" for o in SCORES),
        "execute as @a run scoreboard players operation @s rw.hours = @s rw.play",
        "execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase",
        "scoreboard players operation @a rw.hours /= #hour rw.const",
        "execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1",
        *(f"execute if score #season rw.day matches {n} run scoreboard players set @a {o} 1"
          for o, (n, _) in SEASON_MARKS.items()),
        f"execute as @a unless score @s rw.lastday = #today rw.day run function {NS}:wardrobe/new_day",
        f"function {NS}:wardrobe/founder/second",
        f"function {NS}:challenges/second",
        f"function {NS}:quest/second",
        f"function {NS}:goal/second",
        f"schedule function {NS}:wardrobe/second 20t replace",
    ]) + "\n"
    f[f"{fn}/day.mcfunction"] = (
        "# A new real day (day_once starts it at midnight UTC; staff can run this for an extra one). Players online\n"
        "# get it within a second.\n"
        "scoreboard players add #today rw.day 1\n")
    f[f"{fn}/day_once.mcfunction"] = "\n".join([
        "# Macro {stamp:YYYYMMDD}: deploy/monkey-day.sh sends it at midnight UTC with that UTC date. Starts the day",
        "# unless the day for that date already started, so a retry after a timeout never makes one date two days.",
        "$execute if score #day.sent rw.day matches $(stamp) run return 0",
        "$scoreboard players set #day.sent rw.day $(stamp)",
        f"function {NS}:wardrobe/day",
    ]) + "\n"
    f[f"{fn}/new_day.mcfunction"] = "\n".join([
        "# This player's first login of the day.",
        "scoreboard players add @s rw.days 1",
        "scoreboard players operation @s rw.lastday = #today rw.day",
    ]) + "\n"

    f[f"{fn}/use.mcfunction"] = "\n".join([
        "# Runs as a player who just used /trigger wardrobe: every value opens the menu.",
        f"function {NS}:wardrobe/menu",
        "scoreboard players set @s wardrobe 0",
        "scoreboard players enable @s wardrobe",
    ]) + "\n"

    # One page, under the 20 lines of open chat: a header (two lines), the counts, this week's challenges (one
    # line each), the server goal, and the first-week quest's line for a player taking it.
    counts: list = [{"text": "", "color": "gray"}]
    for i, (o, what) in enumerate(COUNTED.items()):
        counts += [{"score": {"name": "@s", "objective": o}, "color": "white"},
                   f" {what}" + (", " if i < len(COUNTED) - 1 else "")]
    f[f"{fn}/menu.mcfunction"] = "\n".join([
        "# The menu (/trigger wardrobe, /trigger challenges): the counts, this week's challenges, the server goal,",
        "# and the first-week quest's line for a player taking it.",
        "tellraw @s " + text("", {"text": "\nYour progress", "color": "gold", "bold": True},
                             {"text": "  challenges new every Monday, 12 AM Pacific", "color": "gray"}),
        "tellraw @s " + text(*counts),
        f"function {NS}:challenges/lines",
        f"function {NS}:goal/line",
        f"function {NS}:quest/status",
    ]) + "\n"
    f[f"{fn}/menu_challenges.mcfunction"] = "\n".join([
        "# The challenges page, which /trigger challenges opens (challenges/use): the same menu.",
        f"function {NS}:wardrobe/menu",
    ]) + "\n"

    f.update(founder_files())
    f.update(challenges.datapack_files())
    f.update(quest.datapack_files())
    f.update(goal.datapack_files())
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def founder_files() -> dict[str, str]:
    """The launch weekend's window for the launch-weekend founder mark (rw.launch; docs/RETENTION.md, "The launch
    weekend").

    While it is open, everyone online counts seconds in rw.launchtime; FOUNDER_MINUTES of them set rw.launch.
    It shuts when game time passes #founder.until. Game time stops while the server is empty, so
    deploy/monkey-week.sh sends `founder/sync` every hour with the seconds left on the wall clock (from
    tools/challenges.py), and the window ends at the end of Sunday, Pacific, even after a quiet night. State is in
    rw.day: #founder.open, #founder.auto (1 while the clock may move the end) and #founder.until.
    """
    fn = f"data/{NS}/function/wardrobe/founder"
    ticks = LAUNCH_SECONDS * 20
    season_one = ("execute unless score #season rw.day matches 1 run return run tellraw @s "
                  + text({"text": "The launch weekend's window is only for Season I.", "color": "red"}))
    gold = "gold"
    return {
        f"{fn}/open.mcfunction": "\n".join([
            "# Opens the launch weekend: monkey:rules/launch runs this (staff can too, if the launch didn't). Season I",
            f"# only. It lasts {LAUNCH_SECONDS // 3600} hours of game time; deploy/monkey-week.sh moves the end to "
            "the end of Sunday,",
            "# Pacific, on the wall clock.",
            season_one,
            "scoreboard players set #founder.open rw.day 1",
            "scoreboard players set #founder.auto rw.day 1",
            "execute store result score #founder.until rw.day run time query gametime",
            f"scoreboard players add #founder.until rw.day {ticks}",
            "tellraw @a " + text({"text": "Launch weekend: ", "color": gold},
                                 {"text": f"play {FOUNDER_MINUTES} minutes before the end of Sunday (Pacific) to be "
                                          "counted a launch-weekend founder, for good.", "color": "yellow"}),
        ]) + "\n",
        f"{fn}/open_for.mcfunction": "\n".join([
            "# Macro {hours:N}, staff only: opens the window (or keeps it open) for N hours of game time from now.",
            "# The wall clock no longer moves its end; founder/close shuts it early. Season I only.",
            season_one,
            "$scoreboard players set #founder.until rw.day $(hours)",
            "scoreboard players operation #founder.until rw.day *= #hour rw.const",
            "execute store result score #founder.now rw.day run time query gametime",
            "scoreboard players operation #founder.until rw.day += #founder.now rw.day",
            "scoreboard players set #founder.open rw.day 1",
            "scoreboard players set #founder.auto rw.day 0",
            "$tellraw @a " + text({"text": "Launch weekend: ", "color": gold},
                                  {"text": f"open for $(hours) more hours. Play {FOUNDER_MINUTES} minutes to be "
                                           "counted a launch-weekend founder.", "color": "yellow"}),
        ]) + "\n",
        f"{fn}/close.mcfunction": "\n".join([
            "# Shuts the window: by itself when the time is up, from founder/sync at the end of Sunday, or staff.",
            "scoreboard players set #founder.open rw.day 0",
            "scoreboard players set #founder.auto rw.day 0",
            "tellraw @a " + text({"text": "The launch weekend is over. ", "color": gold},
                                 {"text": "Everyone who played it stays a launch-weekend founder.",
                                  "color": "yellow"}),
        ]) + "\n",
        f"{fn}/sync.mcfunction": "\n".join([
            "# Macro {seconds:N}, from deploy/monkey-week.sh every hour: N seconds of the launch weekend are left on",
            "# the wall clock. An open window the launch opened ends then (0 shuts it now); otherwise nothing.",
            "execute unless score #founder.auto rw.day matches 1 run return 0",
            "$scoreboard players set #founder.left rw.day $(seconds)",
            f"execute if score #founder.left rw.day matches ..0 run return run function {NS}:wardrobe/founder/close",
            "scoreboard players operation #founder.left rw.day *= #second rw.const",
            "execute store result score #founder.until rw.day run time query gametime",
            "scoreboard players operation #founder.until rw.day += #founder.left rw.day",
        ]) + "\n",
        f"{fn}/second.mcfunction": "\n".join([
            "# Once a second, from the wardrobe's: while the window is open, count everyone online.",
            "execute unless score #founder.open rw.day matches 1 run return 0",
            "execute store result score #founder.now rw.day run time query gametime",
            "execute if score #founder.now rw.day >= #founder.until rw.day run return run "
            f"function {NS}:wardrobe/founder/close",
            "scoreboard players add @a rw.launchtime 1",
            "tellraw @a[scores={rw.launchtime=1}] " + text(
                {"text": "Launch weekend: ", "color": gold},
                {"text": f"stay {FOUNDER_MINUTES} minutes in all to be counted a launch-weekend founder.",
                 "color": "yellow"}),
            f"scoreboard players set @a[scores={{rw.launchtime={FOUNDER_MINUTES * 60}..}}] rw.launch 1",
        ]) + "\n",
    }


# ---------------------------------------------------------------- writing


def packs(repo: Repo) -> dict[Path, dict[str, str | bytes]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- the day (deploy/monkey-day.sh)

# How long monkey-day.service keeps trying one day before it gives up (and the timer's next run starts afresh).
GIVE_UP = dt.timedelta(hours=6)


def day_stamp(when: dt.datetime) -> int:
    """The UTC date `when` falls on, as YYYYMMDD: the day a run starts, so one date is never two days."""
    return int(when.astimezone(server.UTC).strftime("%Y%m%d"))


def day_commands(when: dt.datetime) -> list[str]:
    return [f"function {NS}:wardrobe/day_once {{stamp:{day_stamp(when)}}}"]


def send_day(rcon, when: dt.datetime, pending: Path | None = None, log=print) -> int:
    """Starts the day for `when`'s UTC date (day_once does nothing when it already started). Unlike the week, a
    server that isn't running is a failure (NOT_RUNNING): a missed day is never caught up, so monkey-day.service
    tries again every 10 minutes. With `pending` (monkey-day.service's state file), a date that has failed for
    GIVE_UP is given up (GAVE_UP), so the retries end and the next midnight's run starts afresh."""
    code = server.send_if_running(rcon, day_commands(when), log, required=True,
                                  skipped="server not running: the day isn't started yet")
    if pending is None:
        return code
    if code == 0:
        pending.unlink(missing_ok=True)
        return 0
    stamp, first = day_stamp(when), when
    try:
        was, since = pending.read_text().split()
        if int(was) == stamp:
            first = dt.datetime.fromtimestamp(int(since), server.UTC)
    except (OSError, ValueError):
        pass
    if when - first >= GIVE_UP:
        pending.unlink(missing_ok=True)
        log(f"gave up: the day for {stamp} didn't start in {GIVE_UP.seconds // 3600} hours of tries")
        return server.GAVE_UP
    if first == when:
        try:
            pending.write_text(f"{stamp} {int(when.timestamp())}\n")
        except OSError as e:
            log(f"can't keep the first try's time in {pending} ({e}); it tries again without a limit")
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The wardrobe's day: the command that starts a new day for days played.")
    sub = ap.add_subparsers(dest="command", required=True)
    server.job_subcommands(sub, "sends it to the running server (deploy/monkey-day.sh, at midnight UTC)")
    state = os.environ.get("STATE_DIRECTORY")   # monkey-day.service's StateDirectory=
    sub.choices["send"].add_argument(
        "--pending", type=Path, default=Path(state.split(":")[0]) / "pending" if state else None,
        help="where a failing date's first try is kept, to give up after 6 hours "
             "(default: $STATE_DIRECTORY/pending; none: no limit)")
    args = ap.parse_args(argv)
    return server.run_job(args, day_commands, lambda rcon, when: send_day(rcon, when, args.pending), needs=JOB_PACKS)


if __name__ == "__main__":
    sys.exit(main())
