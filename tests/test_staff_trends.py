"""tools/staff_trends.py: a month of readings, players per day from the game's log, Ledger's counts per hour, the
faction tables, and the panel routes that answer with them."""
import datetime as dt
import gzip
import json
import os
import sqlite3

import pytest
import staff_panel
import staff_trends
from test_staff_panel import box  # noqa: F401 (the fixture: the real panel over HTTP)
from test_staff_report import ledger, place

NOW = dt.datetime(2026, 11, 17, 9, 0, tzinfo=dt.UTC)     # Tuesday 17 Nov, 1 AM Pacific
MOD = {"X-Staff-Role": "moderator"}
HOUR = 3600


def brk(t, who, block, x=0, y=10, z=0, source="player"):
    return (t, "block-break", x, y, z, "overworld", "air", block, source, who, None)


# ---------------------------------------------------------------- a month of readings


def test_readings_fold_into_hours_and_a_restart_loses_nothing():
    base = int(NOW.timestamp()) // HOUR * HOUR - 3 * HOUR
    readings = [[base + 60, 10.0, 15.0, 2, 50.0, 20.0], [base + 1800, 20.0, 40.0, 4, 60.0, None],
                [base + HOUR + 60, None, None, None, 55.0, 30.0], [base + 2 * HOUR, 12.0, 18.0, 1, 50.0, 10.0]]
    first = staff_trends.history({}, {"history": readings}, NOW)
    assert first["hours"][0] == [base, 15.0, 40.0, 3.0, 4, 55.0, 20.0, 2]
    assert first["hours"][1] == [base + HOUR, None, None, None, None, 55.0, 30.0, 1]
    # staff.json has dropped the oldest reading: its hour, which it now holds only part of, keeps what was kept.
    again = staff_trends.history(first, {"history": readings[1:]}, NOW)
    assert again["hours"] == first["hours"]
    # A month later the hour is gone.
    later = staff_trends.history(first, {"history": []}, NOW + dt.timedelta(days=31))
    assert later["hours"] == []


def test_the_hour_staff_json_is_still_filling_is_worked_out_again():
    base = int(NOW.timestamp()) // HOUR * HOUR
    first = staff_trends.history({}, {"history": [[base + 60, 10.0, 10.0, 1, 50.0, 5.0]]}, NOW)
    again = staff_trends.history(first, {"history": [[base + 60, 10.0, 10.0, 1, 50.0, 5.0],
                                                     [base + 180, 20.0, 30.0, 3, 50.0, 5.0]]}, NOW)
    assert again["hours"] == [[base, 15.0, 30.0, 2.0, 3, 50.0, 5.0, 2]]


def test_a_staff_json_of_the_wrong_shape_is_no_reading():
    assert staff_trends.history({}, ["not", "a", "dict"], NOW)["hours"] == []


def test_a_broken_staff_json_keeps_the_hours_there_were():
    kept = {"hours": [[int(NOW.timestamp()) // HOUR * HOUR, 1.0, 2.0, 1.0, 1, 1.0, 1.0, 1], "junk", [1, 2]]}
    assert staff_trends.history(kept, {"history": "nope"}, NOW)["hours"] == kept["hours"][:1]


# ---------------------------------------------------------------- players per day


def log(lines):
    return "".join(f"[{t}] [Server thread/INFO]: {text}\n" for t, text in lines)


@pytest.fixture
def logs(tmp_path):
    live = tmp_path / "live"
    folder = live / "server" / "logs"
    folder.mkdir(parents=True, exist_ok=True)     # the panel's own fixture has one already

    def gz(name, lines):
        with gzip.open(folder / name, "wt", encoding="utf-8") as f:
            f.write(log(lines))

    gz("2026-11-09-1.log.gz", [("20:00:00", "Starting minecraft server version 26.2"),
                               ("20:05:00", "Alpha joined the game"), ("20:10:00", "Bravo joined the game"),
                               ("20:11:00", "<Eve> Carol joined the game"),          # chat never counts
                               ("21:05:00", "Alpha left the game"), ("23:50:00", "Saving the game")])
    gz("2026-11-10-1.log.gz", [("00:30:00", "Bravo left the game"),                 # the log turned over at midnight
                               ("10:00:00", "System chat: Carol joined the game"), ("10:20:00", "Stopping server")])
    latest = folder / "latest.log"
    latest.write_text(log([("09:00:00", "Starting minecraft server version 26.2"),
                           ("09:01:00", "Alpha joined the game"), ("09:31:00", "Alpha left the game"),
                           ("23:00:00", "Dan joined the game")]), encoding="utf-8")
    written = dt.datetime(2026, 11, 16, 23, 30, tzinfo=staff_trends.calendar.PACIFIC).timestamp()
    os.utime(latest, (written, written))
    return live


def test_sessions_come_from_join_and_leave_lines(logs):
    data = staff_trends.players(logs, {}, NOW)
    days, first = staff_trends.merged_days(data)
    assert days["2026-11-09"]["minutes"] == {"Alpha": 60, "Bravo": 230}       # Bravo's evening, to midnight
    assert days["2026-11-10"]["minutes"] == {"Bravo": 30, "Carol": 20}        # the rest of it, and a stop
    assert sorted(days["2026-11-09"]["sessions"]) == [60, 260]
    assert days["2026-11-16"]["minutes"]["Alpha"] == 30
    assert days["2026-11-16"]["minutes"]["Dan"] == 60 and days["2026-11-17"]["minutes"]["Dan"] == 60   # on till now
    assert first == {"Alpha": "2026-11-09", "Bravo": "2026-11-09", "Carol": "2026-11-10", "Dan": "2026-11-16"}
    assert data["base"]["read"] == ["2026-11-09-1.log.gz", "2026-11-10-1.log.gz"]
    assert "Dan" not in data["base"]["first"]           # latest.log is kept apart, read again each time


def test_a_finished_log_is_read_once(logs, monkeypatch):
    data = staff_trends.players(logs, {}, NOW)
    read = []
    real = staff_trends.staff_report.read_log
    monkeypatch.setattr(staff_trends.staff_report, "read_log", lambda p, d: read.append(p.name) or real(p, d))
    again = staff_trends.players(logs, json.loads(json.dumps(data)), NOW + dt.timedelta(minutes=10))
    assert read == []                   # the finished logs aren't read again; latest.log goes on from its place
    assert staff_trends.merged_days(again)[0]["2026-11-09"] == staff_trends.merged_days(data)[0]["2026-11-09"]


def test_latest_log_keeps_only_the_lines_it_needs_and_goes_on_from_its_place(logs):
    latest = logs / "server" / "logs" / "latest.log"
    lines, mark, went_on = staff_trends.latest_lines(latest, None)
    assert not went_on and mark["offset"] == latest.stat().st_size and mark["day"] == "2026-11-16"
    assert [t for _, t in lines] == ["Starting minecraft server version 26.2", "Alpha joined the game",
                                     "Alpha left the game", "Dan joined the game"]
    assert staff_trends.latest_lines(latest, mark)[:2] == ([], mark)     # unchanged: nothing read
    with open(latest, "a", encoding="utf-8") as f:
        f.write(log([("23:40:00", "Saving the game"), ("00:10:00", "Dan left the game")]) + "[00:11:00] [Ser")
    lines, mark2, went_on = staff_trends.latest_lines(latest, mark)
    # Only the new lines, past midnight on the next day; the line not finished yet waits.
    assert went_on and lines == [(dt.datetime(2026, 11, 17, 0, 10), "Dan left the game")]
    assert mark2["offset"] < latest.stat().st_size and mark2["day"] == "2026-11-17"
    latest.write_text(log([("01:00:00", "Starting minecraft server version 26.2")]), encoding="utf-8")
    assert not staff_trends.latest_lines(latest, mark2)[2]               # a new file: read from its start


def test_the_next_run_reads_latest_log_from_its_place(logs, monkeypatch):
    data = json.loads(json.dumps(staff_trends.players(logs, {}, NOW)))
    with open(logs / "server" / "logs" / "latest.log", "a", encoding="utf-8") as f:
        f.write(log([("23:59:00", "Dan left the game")]))
    seen = []
    real = staff_trends.latest_lines
    monkeypatch.setattr(staff_trends, "latest_lines", lambda p, m: seen.append(m) or real(p, m))
    again = staff_trends.players(logs, data, NOW + dt.timedelta(minutes=10))
    assert seen == [data["live"]["mark"]]
    days, _ = staff_trends.merged_days(again)
    assert days["2026-11-16"]["minutes"]["Dan"] == 59
    assert "Dan" not in days.get("2026-11-17", {"minutes": {}})["minutes"]
    assert 59 in days["2026-11-16"]["sessions"]


def test_a_server_that_stopped_without_a_word_ends_the_sessions_where_it_last_spoke(tmp_path):
    folder = tmp_path / "server" / "logs"
    folder.mkdir(parents=True)
    for name, lines in (("2026-11-12-1.log.gz", [("10:00:00", "Alpha joined the game"), ("10:45:00", "tick")]),
                        ("2026-11-12-2.log.gz", [("12:00:00", "Starting minecraft server version 26.2")])):
        with gzip.open(folder / name, "wt", encoding="utf-8") as f:
            f.write(log(lines))
    days, _ = staff_trends.merged_days(staff_trends.players(tmp_path, {}, NOW))
    assert days["2026-11-12"]["minutes"] == {"Alpha": 45}


def test_the_tenth_log_of_a_day_comes_after_the_ninth():
    assert staff_trends._order("2026-11-09-10.log.gz") > staff_trends._order("2026-11-09-9.log.gz")


def test_retention_counts_who_joined_again_after_1_and_7_days(logs):
    days, first = staff_trends.merged_days(staff_trends.players(logs, {}, NOW))
    rows = staff_trends.retention(days, first, dt.date(2026, 11, 17))
    assert rows[0] == {"week": "2026-11-09", "new": 3, "partial": False, "due_1d": 3, "back_1d": 1, "due_7d": 3,
                       "back_7d": 1}
    # Dan's evening ran past midnight: that is one visit, not a return.
    assert rows[1] == {"week": "2026-11-16", "new": 1, "partial": False, "due_1d": 1, "back_1d": 0, "due_7d": 0,
                       "back_7d": 0}


def test_the_week_the_logs_begin_is_partial_and_its_first_day_left_out(logs):
    data = staff_trends.players(logs, {}, NOW)
    assert data["start"] == "2026-11-09"
    days, first = staff_trends.merged_days(data)
    rows = staff_trends.retention(days, first, dt.date(2026, 11, 17), data["start"])
    # Alpha and Bravo may have played before the logs began: only Carol is new that week.
    assert rows[0] == {"week": "2026-11-09", "new": 1, "partial": True, "due_1d": 1, "back_1d": 0, "due_7d": 1,
                       "back_7d": 0}
    assert not rows[1]["partial"]


def test_a_first_day_that_is_no_date_is_left_out():
    days = {"2026-11-09": {"minutes": {"A": 5}, "sessions": [5], "joined": ["A"]}, "junk": {"minutes": {}}}
    assert staff_trends.retention(days, {"A": "not a day", "B": 7}, dt.date(2026, 11, 17)) == []
    merged, first = staff_trends.merged_days({"base": {"days": days, "first": {"A": "x"}},
                                              "live": {"days": {}, "first": {}}})
    assert "junk" not in merged and first == {}


def test_first_days_older_than_a_year_are_forgotten(logs):
    old = {"version": 1, "base": {"first": {"Gone": "2025-01-01", "Kept": "2026-06-01"}, "start": "2025-01-01"}}
    data = staff_trends.players(logs, old, NOW)
    assert "Gone" not in data["base"]["first"] and data["base"]["first"]["Kept"] == "2026-06-01"
    assert data["start"] == "2025-01-01"                # the day the logs began stays


# ---------------------------------------------------------------- Ledger's counts


@pytest.fixture
def world(tmp_path):
    live = tmp_path / "live"
    (live / "server" / "world").mkdir(parents=True, exist_ok=True)
    rows = [place("2026-11-16 10:05:00", "Alpha", "stone", 1, 64, 1),
            brk("2026-11-16 10:10:00", "Alpha", "diamond_ore"),
            brk("2026-11-16 11:00:00", "Bravo", "stone"),
            brk("2026-11-16 11:01:00", "Bravo", "ancient_debris"),
            brk("2026-11-16 11:02:00", None, "light", source="command"),          # Dynamic Lights: no player
            brk("2026-10-01 11:00:00", "Bravo", "stone")]                         # older than the month
    ledger(live / "server" / "world" / "ledger.sqlite", rows)
    return live


def test_ledger_rows_are_counted_per_hour_and_per_player(world):
    data = staff_trends.world(world, {}, NOW)
    assert data["caught_up"] and data["rows"] == 5
    assert data["hours"] == {"2026-11-16 10": [1, 1], "2026-11-16 11": [2, 0]}
    assert data["days"] == {"2026-11-16": {"Alpha": [1, 1, 0, 1, 0], "Bravo": [2, 0, 1, 0, 1]}}


def test_the_next_run_reads_only_the_new_rows(world):
    data = json.loads(json.dumps(staff_trends.world(world, {}, NOW)))
    db = sqlite3.connect(world / "server" / "world" / "ledger.sqlite")
    db.execute("insert into actions (action_id, time, x, y, z, world_id, object_id, old_object_id, source, player_id) "
               "select action_id, '2026-11-16 12:00:00.000', x, y, z, world_id, object_id, old_object_id, source, "
               "player_id from actions where id = 2")
    db.commit()
    db.close()
    again = staff_trends.world(world, data, NOW + dt.timedelta(hours=1))
    assert again["rows"] == 1 and again["hours"]["2026-11-16 12"] == [1, 0]
    assert again["days"]["2026-11-16"]["Alpha"] == [2, 1, 0, 2, 0]


def test_the_ledger_read_goes_through_the_player_index_from_the_last_row(world):
    db = sqlite3.connect(world / "server" / "world" / "ledger.sqlite")
    plan = " ".join(r[-1] for r in db.execute(
        "explain query plan select id from actions indexed by actions_player_id where player_id = ? and id > ? "
        "order by id limit ?", (1, 0, 10)))
    db.close()
    assert "actions_player_id (player_id=? AND rowid>?)" in plan and "TEMP B-TREE" not in plan


def test_a_capped_run_stops_and_the_next_one_goes_on(world, monkeypatch):
    monkeypatch.setattr(staff_trends, "WORLD_CHUNK", 1)
    first = json.loads(json.dumps(staff_trends.world(world, {}, NOW, most=1)))
    assert not first["caught_up"]
    done = first
    for _ in range(10):
        done = json.loads(json.dumps(staff_trends.world(world, done, NOW, most=1)))
        if done["caught_up"]:
            break
    assert done["caught_up"] and done["hours"] == {"2026-11-16 10": [1, 1], "2026-11-16 11": [2, 0]}


def test_without_the_player_index_the_hourly_gate_still_applies(world):
    db = sqlite3.connect(world / "server" / "world" / "ledger.sqlite")
    db.execute("drop index actions_player_id")
    db.commit()
    db.close()
    data = staff_trends.world(world, {}, NOW)
    assert data["caught_up"] and "no player_id index" in data["note"]
    assert not staff_trends.due(json.loads(json.dumps(data)), staff_trends.WORLD_EVERY, NOW + dt.timedelta(minutes=2))


def test_a_busy_ledger_keeps_what_was_counted(world, monkeypatch):
    real = staff_trends.staff_report.Ledger

    class Busy:
        """Ledger's database, locked by the game after the first query."""
        def __init__(self, db):
            self.db, self.calls = db, 0

        def execute(self, *a):
            self.calls += 1
            if self.calls > 1:
                raise sqlite3.OperationalError("database is locked")
            return self.db.execute(*a)

        def __getattr__(self, name):
            return getattr(self.db, name)

    def opened(path):
        led = real(path)
        led.db = Busy(led.db)
        return led

    monkeypatch.setattr(staff_trends.staff_report, "Ledger", opened)
    monkeypatch.setattr(staff_trends, "WORLD_CHUNK", 1)
    data = staff_trends.world(world, {}, NOW)
    assert not data["caught_up"] and data["rows"] == 1 and "busy" in data["note"]
    assert sum(sum(v) for v in data["hours"].values()) == 1 and data["cursors"]


def test_a_run_that_left_work_goes_on_at_the_next_pass_not_an_hour_later():
    ran = {"version": 1, "at": "2026-11-17T09:00:00Z", "caught_up": True}
    assert not staff_trends.due(ran, staff_trends.WORLD_EVERY, NOW + dt.timedelta(minutes=2))
    assert staff_trends.due({**ran, "caught_up": False}, staff_trends.WORLD_EVERY, NOW + dt.timedelta(minutes=2))
    assert staff_trends.due(ran, staff_trends.WORLD_EVERY, NOW + dt.timedelta(hours=1))

# ---------------------------------------------------------------- the job


def test_update_writes_each_part_and_a_missing_source_spoils_none(tmp_path, logs):
    staff = tmp_path / "staff"
    staff.mkdir()
    (staff / "staff.json").write_text(json.dumps({"version": 2, "history": [[int(NOW.timestamp()), 1, 2, 3, 4, 5]]}))
    said = staff_trends.update(logs, staff, NOW)
    assert said[0].startswith("history: 1 hours") and said[1].startswith("players:")
    assert said[2] == "world: its source isn't there yet"
    assert {p.name for p in (staff / "trends").iterdir()} == {"history.json", "players.json"}
    assert staff_trends.update(logs, staff, NOW + dt.timedelta(minutes=2))[1] == "players: not due yet"
    if os.name != "nt":
        assert (staff / "trends" / "players.json").stat().st_mode & 0o777 == 0o600


def test_a_kept_file_of_the_wrong_shape_starts_that_part_again_and_the_others_go_on(tmp_path, logs, world):
    staff = tmp_path / "staff"
    staff_trends.save(staff / "trends" / "players.json",
                      {"version": 1, "at": "2026-11-17T08:00:00Z", "caught_up": True,
                       "base": {"days": {"2026-11-09": []}, "first": {}}, "live": {"days": {}, "first": {}}})
    staff_trends.save(staff / "trends" / "history.json", {"version": 1, "hours": "nope"})
    said = staff_trends.update(logs, staff, NOW)  # world: the same live folder
    assert said[1].startswith("players: ") and "started again" in said[1]
    assert said[2].startswith("world: ")            # the run went on past it
    again = staff_trends.load(staff / "trends" / "players.json")
    assert staff_trends.readable("players", again, NOW) and again["base"]["days"]["2026-11-09"]["minutes"]
    # The state the review found: a day that is not a dict made make() itself fail.
    staff_trends.save(staff / "trends" / "players.json", {**again, "base": {**again["base"], "last": "not a time"}})
    said = staff_trends.update(logs, staff, NOW + dt.timedelta(minutes=20))
    assert "started again" in said[1] and "not updated" not in said[1]


def test_a_damaged_file_answers_503_not_500(box):  # noqa: F811
    staff_trends.save(box.staff / "trends" / "players.json",
                      {"version": 1, "base": {"days": {"2026-11-09": 5}, "first": {}}, "live": {}})
    assert box.call("GET", "/api/trend-players", headers=MOD)[0] == 503


def test_show_writes_nothing(tmp_path, logs):
    staff = tmp_path / "staff"
    staff_trends.update(logs, staff, NOW, write=False)
    assert not (staff / "trends").exists()


# ---------------------------------------------------------------- the routes


def test_every_route_is_registered_for_moderators():
    for key in staff_trends.ROUTES:
        assert staff_panel.ROUTES[key] is staff_trends.ROUTES[key] and staff_panel.NEEDS[key] == "moderator"


def test_no_trends_yet_says_so(box):  # noqa: F811
    code, answer = box.call("GET", "/api/trend-history", headers=MOD)
    assert code == 404 and "No trends yet" in answer["error"]


def test_the_routes_answer_from_the_files(box, logs, world):  # noqa: F811
    staff = box.staff
    staff_trends.save(staff / "trends" / "players.json", staff_trends.players(logs, {}, NOW))
    staff_trends.save(staff / "trends" / "world.json", staff_trends.world(world, {}, NOW))
    now = dt.datetime.now(dt.UTC)       # the route asks for the last days from the real clock
    staff_trends.save(staff / "trends" / "history.json", staff_trends.history(
        {}, {"history": [[int(now.timestamp()), 10.0, 12.0, 2, 40.0, 5.0]]}, now))
    code, answer = box.call("GET", "/api/trend-history?days=7", headers=MOD)
    assert code == 200 and len(answer["hours"]) == 1 and answer["columns"][1] == "avg"
    code, answer = box.call("GET", "/api/trend-players?days=45", headers=MOD)
    assert code == 200 and {"day", "unique", "new", "hours", "sessions"} <= set(answer["days"][0])
    assert answer["retention"][0]["week"] == "2026-11-09"
    for path in ("/api/trend-world", "/api/trend-ores"):
        assert box.call("GET", path, headers=MOD)[0] == 200
    assert box.call("GET", "/api/trend-players?days=0", headers=MOD)[0] == 400
    assert box.call("GET", "/api/trend-world?days=x", headers=MOD)[0] == 400


def test_players_per_day_and_session_lengths(box, logs):  # noqa: F811
    staff_trends.save(box.staff / "trends" / "players.json", staff_trends.players(logs, {}, NOW))
    answer = staff_trends.trend_players(box.panel, {}, NOW)
    nine = next(r for r in answer["days"] if r["day"] == "2026-11-09")
    # The logs begin that day: who was new can't be told.
    assert nine == {"day": "2026-11-09", "unique": 2, "new": None, "hours": 4.8, "sessions": 2,
                    "median_minutes": 160}
    assert next(r for r in answer["days"] if r["day"] == "2026-11-10")["new"] == 1
    counts = {b["bucket"]: b["count"] for b in answer["session_lengths"]}
    # Dan is still on: his evening so far counts in his hours, not as a finished session.
    assert counts == {"under 10 min": 0, "10-30 min": 1, "30-60 min": 1, "1-2 h": 1, "2-4 h": 0, "4 h and more": 1}
    assert next(r for r in answer["days"] if r["day"] == "2026-11-16")["sessions"] == 1


def test_top_miners_and_the_ore_hint(box, world):  # noqa: F811
    staff_trends.save(box.staff / "trends" / "world.json", staff_trends.world(world, {}, NOW))
    answer = staff_trends.trend_world(box.panel, {"days": "2"}, NOW)
    assert answer["week"] == "2026-11-16" and answer["top_miners"][0] == {"name": "Bravo", "broken": 2, "placed": 0}
    assert answer["hours"][0] == ["2026-11-16 10", 1, 1]
    ores = staff_trends.trend_ores(box.panel, {}, NOW)
    assert {r["name"]: (r["diamond"], r["debris"], r["per_k"]) for r in ores["players"]} == \
        {"Alpha": (1, 0, None), "Bravo": (0, 1, 1000.0)}
    assert not any(r["outlier"] for r in ores["players"])        # one stone is too little to compare


def test_an_outlier_needs_enough_stone_and_the_others_to_compare(box):  # noqa: F811
    cells = {"A": [0, 0, 1000, 30, 0], "B": [0, 0, 1000, 2, 0], "C": [0, 0, 1000, 3, 0], "D": [0, 0, 1000, 2, 0]}
    staff_trends.save(box.staff / "trends" / "world.json",
                      {"version": 1, "at": "x", "days": {"2026-11-16": cells}, "hours": {}, "caught_up": True})
    rows = {r["name"]: r for r in staff_trends.trend_ores(box.panel, {}, NOW)["players"]}
    assert rows["A"]["outlier"] and not rows["B"]["outlier"]


def test_standings_over_time_leave_the_members_out(box):  # noqa: F811
    weeks = box.tmp / "standings" / "weeks"
    weeks.mkdir(parents=True)
    (weeks / "2026-11-15.json").write_text(json.dumps({
        "start": "2026-11-08T17:00:00-08:00", "end": "2026-11-15T17:00:00-08:00", "launched": True,
        "rows": [{"name": "Reds", "members": ["Alpha", "Bravo"], "cup": 3, "strength": 40, "kills": 2, "bounties": 0,
                  "outposts": 1, "points": 101, "rank": 1, "id": "p1"}]}))
    (weeks / "notes.txt").write_text("not a week")
    box.panel.standings = box.tmp / "standings"
    code, answer = box.call("GET", "/api/trend-standings", headers=MOD)
    assert code == 200 and answer["weeks"][0]["rows"][0]["points"] == 101
    assert "members" not in answer["weeks"][0]["rows"][0] and "Alpha" not in json.dumps(answer)
