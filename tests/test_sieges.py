"""Siege windows (tools/sieges.py): when they open, the clock the timer sends, the pack, the VPS units."""
import datetime as dt
import json
import re

import pytest

import datapacks
import diplomacy
import season_calendar
import sieges
from repo import REPO

FILES = sieges.datapack_files()
DEPLOY = REPO.root / "deploy"


def fn(path: str) -> str:
    return FILES[f"{sieges.FN}/{path}.mcfunction"]


def pacific(*args) -> dt.datetime:
    return dt.datetime(*args, tzinfo=season_calendar.PACIFIC)


def clock_args(when: dt.datetime) -> dict:
    """The macro arguments of the one command the timer sends."""
    [command] = sieges.commands(when)
    m = re.fullmatch(r'function monkey:sieges/clock \{now:(\d+),open:(\d+),close:(\d+),label:"([^"]+)"\}', command)
    assert m, command
    return {"now": int(m[1]), "open": int(m[2]), "close": int(m[3]), "label": m[4]}


# ---------------------------------------------------------------- the windows


def test_the_windows_are_wednesday_evening_and_sunday_afternoon_clear_of_the_event_and_the_close():
    # Wednesday 11 November 2026 (Season I's first full week)
    assert sieges.window(pacific(2026, 11, 11, 12, 0)) == (pacific(2026, 11, 11, 19, 0), pacific(2026, 11, 11, 21, 0))
    assert sieges.window(pacific(2026, 11, 11, 21, 0)) == (pacific(2026, 11, 15, 15, 0), pacific(2026, 11, 15, 17, 0))
    for weekday, hour, minute in sieges.WINDOWS:
        end = hour * 60 + minute + sieges.LENGTH.total_seconds() / 60
        assert weekday != 5                       # Saturday: the 6 PM event
        assert weekday != 6 or end <= 19 * 60     # Sunday: done before the 7 PM standings close


def test_a_window_open_now_is_the_one_returned_until_its_last_second():
    start, end = pacific(2026, 11, 11, 19, 0), pacific(2026, 11, 11, 21, 0)
    assert sieges.window(start) == (start, end)
    assert sieges.window(end - dt.timedelta(seconds=1)) == (start, end)


def test_the_hours_stay_pacific_across_the_daylight_saving_change():
    # Daylight saving ends Sunday 1 November 2026 at 2 AM: that afternoon's window is still 3 to 5 PM Pacific.
    start, end = sieges.window(pacific(2026, 11, 1, 1, 0))
    assert (start.hour, end.hour, start.utcoffset()) == (15, 17, dt.timedelta(hours=-8))
    assert sieges.window(pacific(2026, 10, 28, 12, 0))[0].utcoffset() == dt.timedelta(hours=-7)


def test_the_label_reads_as_players_say_it():
    assert sieges.label(pacific(2026, 11, 11, 19, 0), pacific(2026, 11, 11, 21, 0)) == "Wednesday 7 to 9 PM Pacific"
    assert sieges.label(pacific(2026, 11, 15, 11, 0), pacific(2026, 11, 15, 13, 0)) == \
        "Sunday 11 AM to 1 PM Pacific"
    assert sieges.label(pacific(2026, 11, 15, 15, 30), pacific(2026, 11, 15, 17, 30)) == \
        "Sunday 3:30 to 5:30 PM Pacific"


def test_recent_lists_the_windows_that_opened_lately():
    sunday = pacific(2026, 11, 15, 18, 0)
    assert sieges.recent(sunday, dt.timedelta(days=1)) == [(pacific(2026, 11, 15, 15, 0), pacific(2026, 11, 15, 17, 0))]
    assert sieges.recent(sunday, dt.timedelta(hours=1)) == []


# ---------------------------------------------------------------- the clock the timer sends


def test_the_timer_always_sends_one_clock_command_with_the_minute():
    when = pacific(2026, 11, 11, 18, 30)
    args = clock_args(when)
    assert args == {"now": int(when.timestamp()) // 60, "open": 30 * 60, "close": 150 * 60,
                    "label": "Wednesday 7 to 9 PM Pacific"}
    # far from any window: still one command, so the minute in game (7-day wars) stays right
    assert clock_args(pacific(2026, 11, 12, 9, 0))["open"] > 0


def test_inside_a_window_open_is_zero_and_close_counts_down():
    args = clock_args(pacific(2026, 11, 11, 20, 15, 30))
    assert args["open"] == 0 and args["close"] == 45 * 60 - 30


def test_the_commands_and_windows_subcommands(capsys):
    assert sieges.main(["commands", "--at", "2026-11-11T18:30:00-08:00"]) == 0
    assert capsys.readouterr().out.startswith("function monkey:sieges/clock {now:")
    assert sieges.main(["windows", "--at", "2026-11-11T19:30:00-08:00"]) == 0
    out = capsys.readouterr().out
    assert "a window is open now" in out and "Wednesday 7 to 9 PM Pacific (11 Nov)" in out


def test_send_skips_a_server_that_is_not_running():
    class Down:
        def running(self):
            return False

        def __call__(self, command):
            raise AssertionError("nothing is sent to a stopped server")
    assert sieges.send(Down(), pacific(2026, 11, 11, 18, 0), log=lambda msg: None) == 0


# ---------------------------------------------------------------- the pack


def test_off_by_default_and_a_restart_keeps_the_switch_and_restores_an_open_window():
    load = fn("load")
    assert "execute unless score #on sg matches 0.. run scoreboard players set #on sg 0" in load
    assert "scoreboard players set #synced sg 0" in load
    assert "execute if score #open sg matches 1 run function monkey:sieges/unlock" in load
    assert ("execute unless score #open sg matches 1 if score #applied sg matches 1 run function monkey:sieges/lock"
            in load)
    assert FILES["data/minecraft/tags/function/load.json"] == datapacks.function_tag("monkey:sieges/load")


def test_unlock_and_lock_set_open_parties_and_claims_default_player_config():
    unlock, lock = fn("unlock"), fn("lock")
    for key, opened, closed in sieges.SETTINGS:
        assert f"opac default-player-config set {key} {opened}\n" in unlock
        assert f"opac default-player-config set {key} {closed}\n" in lock
    assert "scoreboard players set #applied sg 1" in unlock and "scoreboard players set #applied sg 0" in lock
    # only the protection exceptions: never the server's own claims or the wilderness
    assert not re.search(r"server-claims-config|wilderness-config|expired-claims-config", unlock + lock)


def test_the_check_waits_for_the_clock_and_the_launch_then_opens_closes_and_warns_in_order():
    check = fn("check").splitlines()
    assert check[1] == "execute unless score #synced sg matches 1 run return 0"
    assert check[2] == "execute unless score #launched rw.day matches 1 run return 0"
    body = "\n".join(check)
    assert body.index("run function monkey:sieges/close") < body.index("run function monkey:sieges/open")
    warns = [line for line in check if line.endswith("function monkey:sieges/warn")]
    # the 5-minute warning first, so a restart inside it doesn't say "30 minutes"
    assert ["1..300" in warns[0], "1..1800" in warns[1]] == [True, True]
    assert "#w2" in warns[0] and "#w1" in warns[1]


def test_the_seconds_count_down_between_runs_and_the_minute_counts_on():
    second = fn("second")
    assert second.startswith("schedule function monkey:sieges/second 20t replace\n")
    assert "execute if score #opens sg matches 1.. run scoreboard players remove #opens sg 1" in second
    assert "execute if score #sec sg matches 60.. run scoreboard players add #now sg 1" in second
    assert second.rstrip().endswith("execute if score #on sg matches 1 run function monkey:sieges/check")
    clock = fn("clock")
    assert "$scoreboard players set #now sg $(now)" in clock and "scoreboard players set #synced sg 1" in clock
    assert diplomacy.CLOCK == sieges.NOW == "#now sg"


def test_open_and_close_announce_record_the_minute_and_reset_the_warnings():
    opened, closed = fn("open"), fn("close")
    assert "function monkey:sieges/unlock" in opened and "function monkey:sieges/lock" in closed
    assert "scoreboard players operation #opened sg = #now sg" in opened
    assert "scoreboard players operation #closed sg = #now sg" in closed
    assert "scoreboard players set #w1 sg 0" in closed and "scoreboard players set #w2 sg 0" in closed
    assert "tellraw @a" in opened and "title @a title" in opened and "tellraw @a" in closed


def test_staff_off_closes_an_open_window_and_locks():
    off = fn("staff/off")
    assert off.index("scoreboard players set #on sg 0") < off.index("run function monkey:sieges/close")
    assert "execute if score #applied sg matches 1 run function monkey:sieges/lock" in off
    assert "scoreboard players set #on sg 1" in fn("staff/on")


def test_the_trigger_says_off_open_or_the_next_window():
    show = fn("show")
    assert "scoreboard players set @s sieges 0" in show and "scoreboard players enable @s sieges" in show
    assert "Siege windows are off" in show and "A siege window is open now" in show and "Next siege window" in show
    assert "execute as @a[scores={sieges=1..}] run function monkey:sieges/show" in fn("second")


def test_multi_part_messages_start_with_an_empty_root_so_no_style_leaks():
    # In a list, every part inherits the first one's style: a bold first part would make the whole line bold.
    for path, body in FILES.items():
        for m in re.finditer(r"(?:tellraw @[as]|title @a (?:title|subtitle|actionbar)) (\[.*\])$", body, re.M):
            assert json.loads(m[1])[0] == "", path


def test_the_pack_is_generated_and_its_objectives_are_made():
    assert "sieges" in datapacks.GENERATORS
    assert "scoreboard objectives add sg dummy" in fn("load")
    assert "scoreboard objectives add sieges trigger" in fn("load")


# ---------------------------------------------------------------- the VPS units


@pytest.mark.parametrize("name", ["monkey-sieges.sh", "monkey-sieges.service", "monkey-sieges.timer"])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_a_timed_job_that_shows_the_windows():
    text = (DEPLOY / "monkey-sieges.sh").read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert "JOB_TOOL=sieges.py\n" in text and "JOB_SHOW=windows\n" in text and text.endswith('\ntimed_job "$@"\n')
    assert "JOB_WORLD" not in text and "JOB_NONE" not in text   # always one command, no world needed


def test_the_timer_runs_every_five_minutes_as_the_monkey_user():
    timer = (DEPLOY / "monkey-sieges.timer").read_text()
    assert "OnCalendar=*-*-* *:02/5:40\n" in timer and "Persistent=false\n" in timer
    assert sieges.SLOT_MINUTES == 5
    service = (DEPLOY / "monkey-sieges.service").read_text()
    assert "User=monkey\n" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-sieges.sh\n" in service
