import datetime as dt
import re
import shutil
import subprocess

import border
import finale
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
ACT_ONE = dt.datetime(2027, 2, 20, 18, 1, tzinfo=PACIFIC)    # the relaunch's week 2: a minute after the act's time
BEFORE = dt.datetime(2027, 2, 20, 17, 59, tzinfo=PACIFIC)
ACT_TWO = dt.datetime(2027, 3, 13, 18, 1, tzinfo=PACIFIC)
ACT_THREE = dt.datetime(2027, 4, 3, 18, 1, tzinfo=PACIFIC)
START = (6000, 750)                                          # the starting borders: the Overworld's and the Nether's
SET_8000 = "execute in minecraft:overworld run worldborder set 8000 12000"
SET_1000 = "execute in minecraft:the_nether run worldborder set 1000 12000"
SHRINK_TICKS = 6 * 24 * 3600 * 20
BOSS_ON = "There are 2 data pack(s) enabled: [vanilla (built-in)], [file/monkey-boss (world)]"


def make_server(tmp_path, overworld, nether, *scores, spawn=SPAWN):
    """A server folder: the shipped map configs, and a world with these border widths (a number, or (now, target))
    around the pinned spawn (or SPAWN), and these scores."""
    shutil.copytree(DEFAULT_MAPS, tmp_path / map_border.MAPS, dirs_exist_ok=True)
    fake = FakeWorld(tmp_path / "world").scores(*scores)
    nether_centre = NETHER_CENTRE if spawn == SPAWN else (spawn[0] / 8, spawn[1] / 8)
    dims = (("minecraft:overworld", spawn, overworld), ("minecraft:the_nether", nether_centre, nether))
    for dim, centre, size in dims:
        now, target = size if isinstance(size, tuple) else (size, size)
        fake.border(dim, *centre, now, target)
    fake.border("minecraft:the_end", 0.0, 0.0, map_border.NO_BORDER)
    return fake.path


def test_the_acts_follow_the_season_calendar():
    two = border.acts(2)
    assert [(a.at.date(), a.size, a.nether, a.shrinks, a.boss) for a in two] == [
        (dt.date(2027, 2, 20), 8000, 1000, False, False),
        (dt.date(2027, 3, 13), 10000, 1250, False, True),     # the Edgewalker comes with 10000
        (dt.date(2027, 4, 3), 3000, 375, True, False)]        # the closing, a week before the finale
    assert all(a.at.astimezone(PACIFIC).hour == 18 for a in two)
    # 3 April is after daylight saving time starts (14 March 2027): still 6 PM Pacific, an hour earlier in UTC.
    assert [a.at.astimezone(season_calendar.UTC).hour for a in two] == [2, 2, 1]
    assert border.acts(1) == [] and border.acts(3) == []
    said = border.plan(2)
    assert "Saturday 20 February 2027, 6 PM Pacific: opens to 8000 wide, the Nether 1000" in said
    assert "opens to 10000 wide, the Nether 1250, and the border boss rises" in said
    assert "closes in over 6 days to 3000 wide, the Nether 375" in said


def test_the_closing_ends_before_the_finale():
    closing = border.acts(2)[-1]
    assert closing.shrinks and closing.at + dt.timedelta(seconds=border.SHRINK_SECONDS) < finale.finale_at(2)
    assert closing.size > finale.FINAL_SIZE


def test_season_twos_acts_are_its_calendars_border_breaks():
    season_two = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8").split("\n## Season II\n")[1]
    row = r"^\| (\d+) \| [^|]+ \| The border (?:breaks|closes in)[^|]*?(\d+) to (\d+)"
    breaks = re.findall(row, season_two, re.M)
    assert [(int(w), int(new)) for w, _, new in breaks] == list(border.ACTS[2])


def test_season_one_is_left_to_staff(tmp_path):
    """Season I's acts are by hand: a timer installed early sends nothing in a Season I world, even an hour after
    staff grew the border, when the last save still shows the old one (it would start the growth again)."""
    assert 1 not in border.ACTS
    world = make_server(tmp_path, 5000, 625, ("rw.day", "#season", 1), LAUNCHED)
    for when in (dt.datetime(2026, 11, 21, 18, 1, tzinfo=PACIFIC), dt.datetime(2026, 12, 26, 18, 1, tzinfo=PACIFIC)):
        run = border.read_run(world, when)
        assert run.commands == [] and run.maps == [] and run.why == "no border acts for season 1"
        assert border.commands(world, when) == []


def test_a_failed_set_is_not_recorded_so_the_next_hour_tries_again(tmp_path):
    world = make_server(tmp_path, 8000, 1000, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    log, server = [], rcon.Recorder(fail=2)      # the pack list, then the first set
    assert border.send(server, world, ACT_TWO, log.append) == 1
    assert server.sent == [] and "not sent after it: 4 command(s)" in log
    assert any(line.startswith("can't tell whether monkey-boss is on") for line in log)   # so all was tried
    assert border.commands(world, ACT_TWO)[:2] == [SET_8000.replace("8000", "10000"),
                                                    SET_1000.replace("1000", "1250")]   # still due


def test_nothing_before_the_launch_the_act_or_in_a_locked_world(tmp_path):
    world = make_server(tmp_path, *START, SEASON_TWO)
    assert border.commands(world, ACT_ONE) == [] and border.read_run(world, ACT_ONE).why == "the season hasn't launched"
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED)
    assert border.commands(world, BEFORE) == [] and border.read_run(world, BEFORE).why == "no border act yet"
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED, ("ev.state", "#season_locked", 1))
    assert border.commands(world, ACT_ONE) == []
    world = make_server(tmp_path, *START, ("rw.day", "#season", 5), LAUNCHED)
    assert border.read_run(world, ACT_ONE).why == "no border acts for season 5"


def test_before_the_first_act_the_map_is_fitted_to_a_new_seeds_spawn(tmp_path):
    """The shipped masks fit the pinned seed's spawn; a new seed puts it elsewhere, so the first runs after the
    launch fit the map to the starting borders, once they stand still."""
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED, spawn=(1200.0, -560.0))
    assert border.commands(world, BEFORE) == ["bluemap reload"]
    assert border.send(rcon.Recorder(), world, BEFORE, log=lambda _: None) == 0
    assert map_border.main([str(tmp_path), "--check"]) == 0
    assert map_border.Border(1200.0, -560.0, 6000).mask() == {
        fit.id: fit.border.mask() for fit in map_border.fit_maps(tmp_path) if fit.border}["world"]
    # Not while a border is still moving, and nothing at all from a world not yet saved.
    world = make_server(tmp_path / "b", (5000, 6000), 750, SEASON_TWO, LAUNCHED, spawn=(1200.0, -560.0))
    assert border.commands(world, BEFORE) == [] and border.read_run(world, BEFORE).why == "no border act yet"


def test_a_boss_pack_turned_off_still_grows_the_border_and_records_the_act(tmp_path):
    """The act's boss call is left out (and logged) while staff have monkey-boss off: the run doesn't fail on an
    unknown function, and the act is recorded, so it isn't sent again."""
    world = make_server(tmp_path, 8000, 1000, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    sent = border.commands(world, ACT_TWO)
    assert sent[-1].startswith("function monkey:boss/act {act:2,")
    log, server = [], rcon.Recorder({"datapack list enabled": "There are 1 data pack(s) enabled: [vanilla (built-in)]"})
    assert border.send(server, world, ACT_TWO, log.append) == 0
    assert server.sent == ["datapack list enabled", *sent[:4]]          # no boss call
    assert "skipped monkey:boss/act: the monkey-boss data pack is off (staff turned it off)" in log


def test_an_act_grows_both_borders_and_says_so(tmp_path):
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED)
    sent = border.commands(world, ACT_ONE)
    assert sent[:2] == [SET_8000, SET_1000] and sent[2].startswith('tellraw @a {"text":"The border breaks')
    assert sent[3:] == ["scoreboard players set #border_act ev.state 1"]     # no boss on the first act
    server = rcon.Recorder()
    assert border.send(server, world, ACT_ONE, log=lambda _: None) == 0
    assert server.sent == sent                                           # no boss, so no pack list either
    # Two acts due (the server was down for weeks): only the latest counts.
    assert border.commands(world, ACT_TWO)[:2] == [SET_8000.replace("8000", "10000"), SET_1000.replace("1000", "1250")]


def test_the_closing_shrinks_both_borders_over_six_days_with_no_boss(tmp_path):
    world = make_server(tmp_path, 10000, 1250, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 2))
    sent = border.commands(world, ACT_THREE)
    assert sent[:2] == [f"execute in minecraft:overworld run worldborder set 3000 {SHRINK_TICKS}",
                        f"execute in minecraft:the_nether run worldborder set 375 {SHRINK_TICKS}"]
    assert sent[2].startswith('tellraw @a {"text":"The closing has begun: over the next 6 days the border closes in')
    assert sent[3:] == ["scoreboard players set #border_act ev.state 3"]
    # A border already closed in further by hand is left alone; one still opening is set.
    world = make_server(tmp_path, 2500, (900, 1250), SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 2))
    assert border.commands(world, ACT_THREE)[:2] == [
        f"execute in minecraft:the_nether run worldborder set 375 {SHRINK_TICKS}",
        'scoreboard players set #border_act ev.state 3']


def test_the_map_keeps_the_widest_border_through_the_closing(tmp_path):
    """The land outside was open all season: once the closing is under way, or done, the map stays fitted to
    10000 and isn't fitted down to 3000."""
    world = make_server(tmp_path, (9000, 3000), (1100, 375), SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 3))
    run = border.read_run(world, ACT_THREE)
    assert run.commands == [] and run.maps == [] and run.why == "act 3 is done"
    world = make_server(tmp_path, 3000, 375, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 3))
    run = border.read_run(world, ACT_THREE + dt.timedelta(days=6))
    assert run.commands == [] and run.maps == [] and run.why == "act 3 is done"


def test_a_border_is_never_moved_back_and_only_the_dimension_behind_is_set(tmp_path):
    record = "scoreboard players set #border_act ev.state 1"
    world = make_server(tmp_path, (7200, 8000), 750, SEASON_TWO, LAUNCHED)   # the Overworld already growing
    assert border.commands(world, ACT_ONE)[:2] == [SET_1000, record]
    world = make_server(tmp_path, 8500, 1100, SEASON_TWO, LAUNCHED)            # grown further by hand
    assert border.commands(world, ACT_ONE)[:1] == [record]
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    run = border.read_run(world, ACT_ONE)
    assert run.commands == [] and run.maps == [] and run.why == "act 1 is done (the border has moved on since)"


def test_the_map_follows_the_act_then_purges_an_hour_later(tmp_path):
    world = make_server(tmp_path, 8000, 1000, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
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
    world = make_server(tmp_path, (3000, 256), (375, 375), SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 3))
    run = border.read_run(world, finale.finale_at(2) + dt.timedelta(hours=1))
    assert run.commands == [] and run.maps == []


def test_a_stopped_server_gets_nothing_and_nothing_is_written(tmp_path):
    world = make_server(tmp_path, 8000, 1000, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 1))
    log = []
    assert border.send(rcon.Recorder(running=False), world, ACT_ONE, log.append) == 0
    assert log == ["server not running: nothing sent (the next hour tries again)"]
    assert map_border.main([str(tmp_path), "--check"]) == 1 and not (tmp_path / border.PURGE).exists()


def test_status_runs(tmp_path, capsys):
    world = make_server(tmp_path, *START, SEASON_TWO, LAUNCHED)
    assert border.main(["status", str(world), "--at", ACT_ONE.isoformat()]) == 0
    out = capsys.readouterr().out
    assert "act 1, week 2: Saturday 20 February 6 PM Pacific, opens to 8000 (Nether 1000): due" in out
    assert "act 3, week 8: Saturday 3 April 6 PM Pacific, closes in to 3000 (Nether 375): to come" in out
    world = make_server(tmp_path, (9000, 3000), 375, SEASON_TWO, LAUNCHED, ("ev.state", "#border_act", 3))
    assert border.main(["status", str(world), "--at", ACT_THREE.isoformat()]) == 0
    assert "minecraft:overworld: 9000 wide, closing in to 3000" in capsys.readouterr().out


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
