import datetime as dt
import re
import shutil
import subprocess

import border
import pytest
from fake_world import FakeWorld
from test_deploy_lib import job, needs_dash, sh  # noqa: F401 (sh is test_deploy_lib's fixture)
from test_map_border import DEFAULT_MAPS, NETHER_CENTRE, SPAWN

import map_border
import rcon
import season_calendar
from repo import REPO

PACIFIC = season_calendar.PACIFIC
LAUNCHED = ("rw.day", "#launched", 1)
SEASON_TWO = ("rw.day", "#season", 2)
ACT_ONE = dt.datetime(2027, 2, 20, 18, 1, tzinfo=PACIFIC)    # Season II, week 2: a minute after the act's time
BEFORE = dt.datetime(2027, 2, 20, 17, 59, tzinfo=PACIFIC)
ACT_TWO = dt.datetime(2027, 4, 3, 18, 1, tzinfo=PACIFIC)
SET_4000 = "execute in minecraft:overworld run worldborder set 4000 600"
SET_500 = "execute in minecraft:the_nether run worldborder set 500 600"


def make_server(tmp_path, overworld, nether, *scores):
    """A server folder: the shipped map configs, and a world with these border widths (a number, or (now, target))
    around the pinned spawn, and these scores."""
    shutil.copytree(DEFAULT_MAPS, tmp_path / map_border.MAPS, dirs_exist_ok=True)
    fake = FakeWorld(tmp_path / "world").scores(*scores)
    dims = (("minecraft:overworld", SPAWN, overworld), ("minecraft:the_nether", NETHER_CENTRE, nether))
    for dim, centre, size in dims:
        now, target = size if isinstance(size, tuple) else (size, size)
        fake.border(dim, *centre, now, target)
    fake.border("minecraft:the_end", 0.0, 0.0, map_border.NO_BORDER)
    return fake.path


def test_the_acts_follow_the_season_calendar():
    two = border.acts(2)
    assert [(a.at.date(), a.size, a.nether) for a in two] == [
        (dt.date(2027, 2, 20), 4000, 500), (dt.date(2027, 4, 3), 6000, 750)]
    assert all(a.at.astimezone(PACIFIC).hour == 18 for a in two)
    # 3 April is after daylight saving time starts (14 March 2027): still 6 PM Pacific, an hour earlier in UTC.
    assert [a.at.astimezone(season_calendar.UTC).hour for a in two] == [2, 1]
    assert border.acts(1) == [] and border.acts(3) == []
    assert "Saturday 20 February 2027, 6 PM Pacific: 4000 wide, the Nether 500" in border.plan(2)


def test_season_twos_acts_are_its_calendars_border_breaks():
    season_two = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8").split("\n## Season II\n")[1]
    row = r"^\| (\d+) \| [^|]+ \| The border breaks[^|]*?(\d{4}) to (\d{4})"
    breaks = re.findall(row, season_two, re.M)
    assert [(int(w), int(new)) for w, _, new in breaks] == list(border.ACTS[2])


def test_season_one_is_left_to_staff(tmp_path):
    """Season I's acts are by hand: a timer installed early sends nothing in a Season I world, even an hour after
    staff grew the border, when the last save still shows the old one (it would start the growth again)."""
    assert 1 not in border.ACTS
    world = make_server(tmp_path, 2500, 312.5, ("rw.day", "#season", 1), LAUNCHED)
    for when in (dt.datetime(2026, 11, 21, 18, 1, tzinfo=PACIFIC), dt.datetime(2026, 12, 26, 18, 1, tzinfo=PACIFIC)):
        run = border.read_run(world, when)
        assert run.commands == [] and run.maps == [] and run.why == "no border acts for season 1"
        assert border.commands(world, when) == []


def test_a_failed_set_is_not_recorded_so_the_next_hour_tries_again(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED)
    log, server = [], rcon.Recorder(fail=1)
    assert border.send(server, world, ACT_ONE, log.append) == 1
    assert server.sent == [] and "not sent after it: 3 command(s)" in log
    assert border.commands(world, ACT_ONE)[:2] == [SET_4000, SET_500]   # still due


def test_nothing_before_the_launch_the_act_or_in_a_locked_world(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO)
    assert border.commands(world, ACT_ONE) == [] and border.read_run(world, ACT_ONE).why == "the season hasn't launched"
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED)
    assert border.commands(world, BEFORE) == [] and border.read_run(world, BEFORE).why == "no border act yet"
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED, ("ev.state", "#season_locked", 1))
    assert border.commands(world, ACT_ONE) == []
    world = make_server(tmp_path, 2500, 312.5, ("rw.day", "#season", 5), LAUNCHED)
    assert border.read_run(world, ACT_ONE).why == "no border acts for season 5"


def test_an_act_grows_both_borders_and_says_so(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED)
    sent = border.commands(world, ACT_ONE)
    assert sent[:2] == [SET_4000, SET_500] and sent[2].startswith('tellraw @a {"text":"The border breaks')
    assert sent[3:] == ["scoreboard players set #border_act ev.state 1"]
    server = rcon.Recorder()
    assert border.send(server, world, ACT_ONE, log=lambda _: None) == 0 and server.sent == sent
    # Two acts due (the server was down for weeks): only the latest counts.
    assert border.commands(world, ACT_TWO)[:2] == [SET_4000.replace("4000", "6000"), SET_500.replace("500", "750")]


def test_a_border_is_never_shrunk_and_only_the_dimension_behind_is_set(tmp_path):
    record = "scoreboard players set #border_act ev.state 1"
    world = make_server(tmp_path, (3000, 4000), 312.5, SEASON_TWO, LAUNCHED)   # the Overworld already growing
    assert border.commands(world, ACT_ONE) == [SET_500, record]
    world = make_server(tmp_path, 5000, 600, SEASON_TWO, LAUNCHED)            # grown further by hand
    assert border.commands(world, ACT_ONE) == [record]
    world = make_server(tmp_path, 5000, 600, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    run = border.read_run(world, ACT_ONE)
    assert run.commands == [] and run.maps == [] and run.why == "act 1 is done (the border has moved on since)"


def test_the_map_follows_the_act_then_purges_an_hour_later(tmp_path):
    world = make_server(tmp_path, 4000, 500, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    assert border.commands(world, ACT_ONE) == ["bluemap reload"]
    log, server = [], rcon.Recorder()
    assert border.send(server, world, ACT_ONE, log.append) == 0 and server.sent == ["bluemap reload"]
    assert map_border.main([str(tmp_path), "--check"]) == 0
    assert (tmp_path / border.PURGE).read_text() == "world\nworld_the_nether\n"
    # The next hour: the purges. One BlueMap answers "still loading" stays for the hour after.
    assert border.commands(world, ACT_ONE) == ["bluemap purge world", "bluemap purge world_the_nether"]
    server = rcon.Recorder({"bluemap purge world_the_nether": "BlueMap is still loading"})
    assert border.send(server, world, ACT_ONE, log.append) == 0
    assert (tmp_path / border.PURGE).read_text() == "world_the_nether\n"
    assert border.send(rcon.Recorder(), world, ACT_ONE, log.append) == 0 and not (tmp_path / border.PURGE).exists()
    assert border.commands(world, ACT_ONE) == [] and border.read_run(world, ACT_ONE).why == "act 1 is done"


def test_the_map_is_not_fitted_to_the_finales_shrinking_border(tmp_path):
    world = make_server(tmp_path, (6000, 200), (750, 25), SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 2))
    finale = dt.datetime(2027, 4, 24, 19, 0, tzinfo=PACIFIC)
    run = border.read_run(world, finale)
    assert run.commands == [] and run.maps == []


def test_a_stopped_server_gets_nothing_and_nothing_is_written(tmp_path):
    world = make_server(tmp_path, 4000, 500, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    log = []
    assert border.send(rcon.Recorder(running=False), world, ACT_ONE, log.append) == 0
    assert log == ["server not running: nothing sent (the next hour tries again)"]
    assert map_border.main([str(tmp_path), "--check"]) == 1 and not (tmp_path / border.PURGE).exists()


def test_status_runs(tmp_path, capsys):
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED)
    assert border.main(["status", str(world), "--at", ACT_ONE.isoformat()]) == 0
    out = capsys.readouterr().out
    assert "act 1, week 2: Saturday 20 February 6 PM Pacific, 4000 (Nether 500): due" in out
    assert "act 2, week 8: Saturday 3 April 6 PM Pacific, 6000 (Nether 750): to come" in out


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPT = "monkey-border.sh"
UNITS = ["monkey-border.service", "monkey-border.timer"]


@pytest.mark.parametrize("name", [SCRIPT, *UNITS])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_a_timed_job_and_the_timer_runs_hourly():
    text = (DEPLOY / SCRIPT).read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text and "WEBHOOK" not in text
    assert "JOB_TOOL=border.py\n" in text and "JOB_WORLD=1\n" in text and "JOB_SHOW=status\n" in text
    assert text.endswith('\ntimed_job "$@"\n')
    service = (DEPLOY / "monkey-border.service").read_text()
    assert "User=monkey" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-border.sh\n" in service
    assert "OnCalendar=*-*-* *:01:00" in (DEPLOY / "monkey-border.timer").read_text()
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / SCRIPT)], check=True)


@pytest.fixture
def border_job(request, tmp_path):
    run = request.getfixturevalue("sh")
    (tmp_path / "repo" / "tools").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / "tools" / "border.py").write_text("")
    return lambda *args, **env: job(run, tmp_path, SCRIPT, *args, **env)


@needs_dash
def test_the_timer_with_nothing_due_takes_no_lock(border_job):
    code, logged, calls = border_job()
    assert code == 0 and logged == [] and len(calls) == 1
    assert calls[0].endswith("border.py commands /srv/live/server/world")


@needs_dash
def test_the_timer_sends_under_the_deploy_lock(border_job):
    code, logged, calls = border_job(FAKE_OUT_python3=r"bluemap reload: ok\n")
    assert code == 0 and logged == ["bluemap reload: ok"]
    send = calls.index("flock -w 1800 9") + 1
    assert calls[send].endswith("border.py send /srv/live/server/world --docker /srv/live/docker")
