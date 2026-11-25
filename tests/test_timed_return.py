import datetime as dt
import json
import sqlite3

import pytest

import rcon
import season_calendar
import timed_return as tr

UTC = dt.timezone.utc   # noqa: UP017
PACIFIC = season_calendar.PACIFIC
MIDSEASON = dt.datetime(2027, 3, 1, 12, 0, tzinfo=PACIFIC)
ALEX, SAM = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def live(tmp_path):
    """A live folder: server/world, server/plugins/LifeStealZ/userData.db and docker/."""
    world = tmp_path / "server" / "world"
    world.mkdir(parents=True)
    (tmp_path / "docker").mkdir()
    db = tr.database(world)
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE hearts (uuid CHAR(36) PRIMARY KEY, name VARCHAR(64) NOT NULL, "
                     "maxhp FLOAT NOT NULL DEFAULT 20.0, firstJoin BIGINT NOT NULL DEFAULT 0)")
    return world


def hearts(world, **players):
    with sqlite3.connect(tr.database(world)) as conn:
        conn.execute("DELETE FROM hearts")
        for name, maxhp in players.items():
            conn.execute("INSERT INTO hearts (uuid, name, maxhp) VALUES (?, ?, ?)",
                         ({"Alex": ALEX, "Sam": SAM}.get(name, name), name, maxhp))


def test_the_window_is_the_relaunch_up_to_the_finale():
    assert not tr.in_season(season_calendar.RELAUNCH.launch - dt.timedelta(seconds=1))
    assert tr.in_season(season_calendar.RELAUNCH.launch)
    assert dt.datetime(2027, 4, 10, 18, 0, tzinfo=PACIFIC) == tr.FINALE_AT
    assert tr.in_season(tr.FINALE_AT - dt.timedelta(seconds=1)) and not tr.in_season(tr.FINALE_AT)


def test_the_kept_list_sits_in_the_docker_folder(live):
    assert tr.state_file(live) == live.parent.parent / "docker" / ".monkey-return.json"


def test_no_database_means_nobody_to_bring_back(tmp_path):
    world = tmp_path / "server" / "world"
    world.mkdir(parents=True)
    assert tr.eliminated(tr.database(world)) == {}
    assert tr.commands(world, MIDSEASON) == []


def test_a_player_comes_back_24_hours_after_first_seen_out(live):
    hearts(live, Alex=0.0, Sam=20.0)
    server = rcon.Recorder({"lifestealz:revive": "Alex has been revived"})
    assert tr.send(server, live, MIDSEASON) == 0
    assert server.sent == []                                     # just noted
    kept = json.loads(tr.state_file(live).read_text())
    assert list(kept) == [ALEX] and kept[ALEX]["name"] == "Alex"
    assert tr.commands(live, MIDSEASON + dt.timedelta(hours=23, minutes=59)) == []
    later = MIDSEASON + dt.timedelta(hours=24)
    assert tr.commands(live, later) == ["lifestealz:revive Alex"]
    assert tr.send(server, live, later) == 0
    assert server.sent == ["lifestealz:revive Alex"]
    assert tr.commands(live, later + dt.timedelta(minutes=10)) == []      # sent: not again within RETRY
    hearts(live, Alex=6.0, Sam=20.0)                                     # the database shows them back
    tr.send(server, live, later + dt.timedelta(minutes=10))
    assert json.loads(tr.state_file(live).read_text()) == {}


def test_a_revive_the_plugin_turned_down_is_sent_again(live, capsys):
    hearts(live, Alex=0.0)
    server = rcon.Recorder({"lifestealz:revive": "Player not found"})
    tr.send(server, live, MIDSEASON)
    day = MIDSEASON + dt.timedelta(days=1)
    assert tr.send(server, live, day) == 0 and ALEX in json.loads(tr.state_file(live).read_text())
    assert tr.send(server, live, day + dt.timedelta(minutes=10)) == 0 and len(server.sent) == 1
    assert tr.send(server, live, day + tr.RETRY) == 1                    # still out: again, and the run fails
    assert server.sent == ["lifestealz:revive Alex"] * 2 and "still out after a revive" in capsys.readouterr().out


def test_revived_and_out_again_between_two_runs_starts_a_new_day(live):
    with sqlite3.connect(tr.database(live)) as conn:
        conn.execute("ALTER TABLE hearts ADD COLUMN hasbeenRevived INTEGER NOT NULL DEFAULT 0")
    hearts(live, Alex=0.0)
    tr.send(rcon.Recorder(), live, MIDSEASON)
    with sqlite3.connect(tr.database(live)) as conn:                     # a Revive Beacon, then a death
        conn.execute("UPDATE hearts SET hasbeenRevived = 1")
    tr.send(rcon.Recorder(), live, MIDSEASON + dt.timedelta(hours=23))
    assert tr.commands(live, MIDSEASON + dt.timedelta(hours=24)) == []
    assert tr.commands(live, MIDSEASON + dt.timedelta(hours=47)) == ["lifestealz:revive Alex"]


def test_a_kept_time_that_isnt_a_time_with_a_zone_starts_the_day_again(live):
    hearts(live, Alex=0.0)
    tr.state_file(live).write_text(json.dumps({ALEX: {"name": "Alex", "since": "2027-02-20 18:00"}}))
    assert tr.commands(live, MIDSEASON) == []                            # no crash: the entry is dropped
    tr.send(rcon.Recorder(), live, MIDSEASON)                            # and the day starts now
    assert tr.commands(live, MIDSEASON + dt.timedelta(days=1)) == ["lifestealz:revive Alex"]


def test_commands_change_nothing(live):
    hearts(live, Alex=0.0)
    assert tr.commands(live, MIDSEASON) == []
    assert not tr.state_file(live).exists()


def test_a_revive_some_other_way_drops_them_and_a_new_elimination_starts_a_new_day(live):
    hearts(live, Alex=0.0)
    server = rcon.Recorder()
    tr.send(server, live, MIDSEASON)
    hearts(live, Alex=6.0)                                       # a Revive Beacon
    tr.send(server, live, MIDSEASON + dt.timedelta(hours=2))
    assert json.loads(tr.state_file(live).read_text()) == {}
    hearts(live, Alex=0.0)
    tr.send(server, live, MIDSEASON + dt.timedelta(hours=3))
    assert tr.commands(live, MIDSEASON + dt.timedelta(hours=25)) == []
    assert tr.commands(live, MIDSEASON + dt.timedelta(hours=27)) == ["lifestealz:revive Alex"]
    assert server.sent == []


def test_a_server_that_isnt_running_keeps_them_waiting(live, capsys):
    hearts(live, Alex=0.0)
    tr.send(rcon.Recorder(), live, MIDSEASON)
    down = rcon.Recorder(running=False)
    assert tr.send(down, live, MIDSEASON + dt.timedelta(days=1)) == 0
    assert down.sent == [] and "server not running" in capsys.readouterr().out
    assert ALEX in json.loads(tr.state_file(live).read_text())


def test_a_failed_revive_is_tried_again(live):
    hearts(live, Alex=0.0, Sam=0.0)
    tr.send(rcon.Recorder(), live, MIDSEASON)
    flaky = rcon.Recorder(fail=1)
    assert tr.send(flaky, live, MIDSEASON + dt.timedelta(days=1)) == 1
    assert len(flaky.sent) == 1
    kept = json.loads(tr.state_file(live).read_text())
    assert len(kept) == 2 and sum("tried" in e for e in kept.values()) == 1   # the failed one is due next run


def test_nobody_comes_back_once_the_finale_starts(live):
    hearts(live, Alex=0.0)
    tr.send(rcon.Recorder(), live, tr.FINALE_AT - dt.timedelta(hours=2))
    assert tr.commands(live, tr.FINALE_AT + dt.timedelta(days=1)) == []
    assert "outside the season" in tr.waiting(live, tr.FINALE_AT + dt.timedelta(days=1))[0]


def test_waiting_says_when_each_comes_back(live):
    hearts(live, Alex=0.0)
    tr.send(rcon.Recorder(), live, MIDSEASON)
    assert tr.waiting(live, MIDSEASON + dt.timedelta(hours=1)) == ["Alex: back Tue 2 Mar 12 PM Pacific"]
    hearts(live)
    assert tr.waiting(live, MIDSEASON) == ["nobody is out"]


def test_the_command_line(live, capsys):
    hearts(live, Alex=0.0)
    state = live.parent / "kept.json"
    state.write_text(json.dumps({ALEX: {"name": "Alex", "since": "2027-02-20T00:00:00+00:00"}}))
    assert tr.main(["commands", str(live), "--state", str(state), "--at", "2027-02-22T00:00:00Z"]) == 0
    assert capsys.readouterr().out == "lifestealz:revive Alex\n"
    assert tr.main(["packs-on", "--docker", str(live)]) == 0
    assert "none needed" in capsys.readouterr().out
