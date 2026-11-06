import datetime as dt
import json
import os
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
import staff_status

import rcon
from repo import REPO

DEPLOY = REPO.root / "deploy"
PAGE = DEPLOY / "staff"
UNITS = ["monkey-staff.service", "monkey-staff.timer"]
TICK = ("The game is running normallyTarget tick rate: 20.0 per second.\n"
        "Average time per tick: 12.5ms (Target: 50.0ms)Percentiles: P50: 11.9ms P95: 18.7ms P99: 31.0ms. Sample: 100")
LIST = "There are 3 of a max of 30 players online: Alpha, Bravo, Charlie"
PS = json.dumps({"State": "running", "Status": "Up 3 hours (healthy)", "Health": "healthy", "Name": "monkey"})
MEMINFO = ("MemTotal:       16000000 kB\nMemAvailable:    4000000 kB\n"
           "SwapTotal:       2000000 kB\nSwapFree:        1500000 kB\n")
NOW = rcon.parse_time("2026-11-15T02:00:00Z")
SEED = "1234567890123"
iso = staff_status.public.iso


def docker(ps=PS, ps_code=0, answers=None):
    """The real adapter over a fake `docker compose`: what it runs is what the VPS runs."""
    answers = {"tick query": TICK, "list": LIST} if answers is None else answers

    def run(argv, **_):
        if "ps" in argv:
            return SimpleNamespace(returncode=ps_code, stdout=ps, stderr="")
        command = argv[-1]
        if command in answers:
            return SimpleNamespace(returncode=0, stdout=answers[command], stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="connection refused")
    return rcon.Docker("/srv/live/docker", run=run)


@pytest.fixture
def box(tmp_path):
    """A release's folder and the machine's files, with a backup, an old backup and something that isn't one."""
    live = tmp_path / "live"
    (live / "monkey").mkdir(parents=True)
    (live / "monkey" / "manifest.json").write_text(json.dumps({"version": "3.1.0", "world": {"seed": SEED}}))
    for name, hours_ago in (("2026-11-14_04-00-00", 22), ("2026-11-15_01-00-00", 1), ("notes", 0)):
        when = (NOW - dt.timedelta(hours=hours_ago)).timestamp()
        (live / "backups" / name).mkdir(parents=True)
        os.utime(live / "backups" / name, (when, when))
    (tmp_path / "meminfo").write_text(MEMINFO)
    return SimpleNamespace(live=live, meminfo=tmp_path / "meminfo", settings=tmp_path / "settings",
                           failing=tmp_path / "failing", out=tmp_path / "staff.json")


def read(box, server=None, now=NOW, previous=None):
    return staff_status.status(box.live, now, server or docker(), previous=previous, meminfo=box.meminfo,
                               settings=box.settings, failing=box.failing)


def test_reads_a_running_server(box):
    data = read(box)
    assert data["version"] == 1 and data["checked"] == "2026-11-15T02:00:00Z" and data["online"] is True
    assert data["container"] == {"state": "running", "uptime": "3 hours", "health": "healthy"}
    assert data["tick"] == {"state": "The game is running normally", "target": 20.0, "tps": 20.0, "avg": 12.5,
                            "p50": 11.9, "p95": 18.7, "p99": 31.0, "sample": 100}
    assert data["players"] == {"count": 3, "max": 30, "names": ["Alpha", "Bravo", "Charlie"]}
    assert data["release"] == "3.1.0"
    assert data["host"]["memory"] == {"total": 16000000, "available": 4000000}
    assert data["host"]["swap"] == {"total": 2000000, "free": 1500000}
    assert data["host"]["disk"]["total"] > 0 and data["host"]["threads"] >= 1
    assert data["history"] == [[round(NOW.timestamp()), 12.5, 18.7, 3]]


def test_tps_is_what_the_average_allows_and_never_above_the_target():
    slow = TICK.replace("Average time per tick: 12.5ms", "Average time per tick: 80.0ms")
    assert staff_status.tick(slow)["tps"] == 12.5
    assert staff_status.tick(TICK)["tps"] == 20.0
    assert staff_status.tick(TICK.replace("12.5ms", "0.0ms"))["tps"] == 20.0


def test_the_real_answers_from_the_server_parse():
    """As the VPS answered on 4 November: no space after the first sentence, and nobody on."""
    live = ("The game is running normallyTarget tick rate: 20.0 per second.\nAverage time per tick: 0.4ms "
            "(Target: 50.0ms)Percentiles: P50: 0.4ms P95: 0.7ms P99: 1.1ms. Sample: 100")
    assert staff_status.tick(live)["p99"] == 1.1
    assert staff_status.players("There are 0 of a max of 30 players online: ") == {"count": 0, "max": 30, "names": []}


@pytest.mark.parametrize("answer", ["", "Unknown thing", "Average time per tick: fastms"])
def test_an_answer_it_does_not_know_is_no_reading(answer):
    assert staff_status.tick(answer) is None and staff_status.players(answer) is None


@pytest.mark.parametrize(("ps", "state", "uptime"), [
    ("", "not created", None),
    (json.dumps({"State": "exited", "Status": "Exited (0) 2 minutes ago"}), "exited", None),
    (json.dumps([{"State": "running", "Status": "Up 5 minutes"}]), "running", "5 minutes"),
    (json.dumps({"State": "restarting", "Status": "Restarting (1) 3 seconds ago"}), "restarting", None),
])
def test_what_docker_says_about_the_container(ps, state, uptime):
    assert staff_status.container(docker(ps=ps)) == {"state": state, "uptime": uptime, "health": None}


def test_a_stopped_server_is_not_asked_and_leaves_a_gap(box):
    asked = []
    server = docker(ps=json.dumps({"State": "exited", "Status": "Exited (0) 2 minutes ago"}))
    real = server.run
    server.run = lambda argv, **how: (asked.append(argv), real(argv, **how))[1]
    data = read(box, server)
    assert data["online"] is False and data["tick"] is None and data["players"] is None
    assert data["history"] == [[round(NOW.timestamp()), None, None, None]]
    assert len(asked) == 1 and "ps" in asked[0]


def test_a_running_container_that_will_not_answer_is_not_online(box):
    data = read(box, docker(answers={}))
    assert data["online"] is False and data["container"]["state"] == "running" and data["tick"] is None


def test_docker_failing_is_not_a_stopped_server(box):
    data = read(box, docker(ps="", ps_code=1))
    assert data["online"] is False and data["container"] is None
    assert staff_status.container(docker(ps="not json")) is None


def test_history_carries_over_keeps_a_day_and_holds_no_names(box):
    old = round((NOW - dt.timedelta(hours=25)).timestamp())
    kept = round((NOW - dt.timedelta(hours=23)).timestamp())
    box.out.write_text(json.dumps({"history": [[old, 1.0, 2.0, 1], [kept, 3.0, 4.0, 2], "bad", [1]]}))
    data = read(box, previous=box.out)
    assert [row[0] for row in data["history"]] == [kept, round(NOW.timestamp())]
    assert "Alpha" not in json.dumps(data["history"])


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"history": 3}'])
def test_an_unreadable_file_starts_the_history_afresh(box, text):
    box.out.write_text(text)
    assert len(read(box, previous=box.out)["history"]) == 1


def test_a_day_of_readings_stays_small(box):
    start = round(NOW.timestamp()) - 86000
    box.out.write_text(json.dumps({"history": [[start + i * 120, 12.5, 18.7, 30] for i in range(716)]}))
    assert len(json.dumps(read(box, previous=box.out), separators=(",", ":"))) < 30_000


def test_the_seed_never_reaches_the_file(box):
    assert SEED not in json.dumps(read(box))
    (box.live / "monkey" / "manifest.json").write_text("[1, 2]")
    assert read(box)["release"] is None
    (box.live / "monkey" / "manifest.json").unlink()
    assert read(box)["release"] is None


# The log. Every line here is made up, in the shape the server's log has.

START = ('[10:00:00] [main/INFO]: Loading Minecraft\n'
         '[10:00:05] [Worker-Main-3/ERROR]: Couldn\'t parse data file made:up\n'
         '[10:00:06] [main/WARN]: Empty or non-existent pool: made:up\n'
         '[10:00:30] [Server thread/INFO]: Done (30.000s)! For help, type "help"\n')


def log(box, text, mode="w"):
    path = box.live / "server" / "logs" / "latest.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8", newline="\n") as f:
        f.write(text)


def problems(box, now=NOW):
    """One reading written to the status file, as the job does it, so that the next one carries on from it."""
    data = read(box, now=now, previous=box.out)
    box.out.write_text(json.dumps(data))
    return data["problems"]


def crash(box, name, hours_ago, text):
    path = box.live / "server" / "crash-reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    when = (NOW - dt.timedelta(hours=hours_ago)).timestamp()
    os.utime(path, (when, when))


def test_errors_after_the_start_are_listed_and_those_during_it_only_counted(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n"
                     "java.lang.RuntimeException: the stack trace\n"
                     "\tat made.up.Thing(Thing.java:1)\n"
                     "[10:01:01] [Server thread/WARN]: Timed out waiting\n"
                     "[10:01:02] [Server thread/INFO]: Alpha joined the game\n")
    found = problems(box)
    assert [row["text"] for row in found["errors"]] == ["Error sending packet"]
    assert found["errors"][0] == {"text": "Error sending packet", "count": 1, "first": iso(NOW), "last": iso(NOW),
                                  "older": True}
    assert found["read"] is True and found["log"]["up"] is True and found["log"]["startup"] == 1
    assert found["lag"] is None and found["crashes"] == []


def test_a_fatal_line_is_listed_even_before_the_start_finishes(box):
    log(box, "[10:00:00] [main/INFO]: Loading Minecraft\n[10:00:05] [main/FATAL]: Failed to start the server\n")
    found = problems(box)
    assert [row["text"] for row in found["errors"]] == ["Failed to start the server"]
    assert found["log"]["up"] is False


def test_falling_behind_is_counted_with_the_worst_of_it(box):
    log(box, "[10:00:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 9000ms or 180 ticks "
             "behind\n" + START +
             "[10:01:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2034ms or 40 ticks "
             "behind\n"
             "[10:02:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 3100ms or 62 ticks "
             "behind\n")
    assert problems(box)["lag"] == {"worst": 3100, "count": 2, "first": iso(NOW), "last": iso(NOW),
                                  "older": True}


@pytest.mark.parametrize("line", [
    "[10:01:00] [Server thread/INFO]: <Alpha> [10:01:00] [Server thread/ERROR]: the server is on fire",
    "[10:01:00] [Server thread/INFO]: [Not Secure] <Alpha> [Server thread/FATAL]: the server is on fire",
    "the server is on fire [10:01:00] [Server thread/ERROR]: the server is on fire",
])
def test_nothing_a_player_says_can_pass_for_an_error(box, line):
    log(box, START + line + "\n")
    assert problems(box)["errors"] == []


def test_a_player_saying_done_does_not_end_the_start(box):
    log(box, "[10:00:00] [main/INFO]: Loading Minecraft\n"
             "[10:00:01] [Server thread/INFO]: <Alpha> Done (1.000s)!\n"
             "[10:00:02] [Render thread/INFO]: Done (1.000s)!\n"
             "[10:00:03] [main/ERROR]: Couldn't parse data file made:up\n")
    found = problems(box)
    assert found["log"]["up"] is False and found["errors"] == [] and found["log"]["startup"] == 1


def test_a_reading_only_reads_what_is_new(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    assert problems(box)["errors"][0]["count"] == 1
    later = NOW + dt.timedelta(minutes=2)
    assert problems(box, later)["errors"][0]["count"] == 1
    log(box, "[10:03:00] [Server thread/ERROR]: Error sending packet\n", "a")
    later += dt.timedelta(minutes=2)
    row = problems(box, later)["errors"][0]
    assert row["count"] == 2 and row["first"] == iso(NOW) and row["last"] == iso(later) and "older" not in row


def test_only_the_first_reading_calls_what_it_finds_older(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    assert problems(box)["errors"][0]["older"] is True
    log(box, "[10:03:00] [Server thread/ERROR]: Something else broke\n", "a")
    rows = {row["text"]: row for row in problems(box, NOW + dt.timedelta(minutes=2))["errors"]}
    assert rows["Error sending packet"]["older"] is True and "older" not in rows["Something else broke"]


def test_a_line_still_being_written_waits_for_its_end(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sen")
    assert problems(box)["errors"] == []
    log(box, "ding packet\n", "a")
    assert [row["text"] for row in problems(box)["errors"]] == ["Error sending packet"]


def test_a_restart_starts_a_new_log_and_keeps_what_was_found(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    problems(box)
    log(box, START.replace("10:00:00", "04:30:00"))     # same length or shorter, another first line
    found = problems(box, NOW + dt.timedelta(hours=3))
    assert [row["count"] for row in found["errors"]] == [1] and found["log"]["up"] is True
    assert found["log"]["startup"] == 1


def test_a_shorter_log_with_the_same_first_line_is_still_a_new_log(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    problems(box)
    log(box, "[10:00:00] [main/INFO]: Loading Minecraft\n[10:00:05] [main/ERROR]: Another start's error\n")
    found = problems(box)
    assert found["log"]["up"] is False and found["log"]["startup"] == 1


def test_what_was_found_goes_a_day_after_its_last_line(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n"
                     "[10:02:00] [Server thread/WARN]: Can't keep up! Running 2034ms or 40 ticks behind\n")
    problems(box)
    assert problems(box, NOW + dt.timedelta(hours=23))["errors"] != []
    box.out.write_text(json.dumps(read(box, now=NOW, previous=None)))
    found = problems(box, NOW + dt.timedelta(hours=24, seconds=1))
    assert found["errors"] == [] and found["lag"] is None


def test_lines_that_differ_only_in_numbers_are_one_group_with_the_latest_text(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Lost chunk 12 at 340\n"
                     "[10:01:01] [Server thread/ERROR]: Lost chunk 7 at 9001\n"
                     "[10:01:02] [Server thread/ERROR]: Lost 0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9\n"
                     "[10:01:03] [Server thread/ERROR]: Lost ffffeeee-4e5f-6071-8293-a4b5c6d7e8f9\n")
    assert {row["text"]: row["count"] for row in problems(box)["errors"]} == {
        "Lost chunk 7 at 9001": 2, "Lost ffffeeee-4e5f-6071-8293-a4b5c6d7e8f9": 2}


def test_only_the_newest_groups_are_kept(box):
    log(box, START + "".join(f"[10:01:00] [Server thread/ERROR]: Broken {'ab'[n % 2] * (n + 1)} thing\n"
                             for n in range(5)))
    problems(box)
    log(box, "".join(f"[10:02:00] [Server thread/ERROR]: Later {chr(97 + n)}x{chr(97 + n)} thing\n"
                     for n in range(26)) + "[10:02:00] [Server thread/ERROR]: Later zebra\n"
                                           "[10:02:00] [Server thread/ERROR]: Later yak\n", "a")
    later = problems(box, NOW + dt.timedelta(minutes=2))["errors"]
    assert len(later) == staff_status.ERRORS_KEPT
    assert all(row["text"].startswith("Later") for row in later[:28])
    assert sum(row["text"].startswith("Broken") for row in later) == 2


@pytest.mark.parametrize("word", ["seed", "level-seed=1", "worldSeed", "SECRET", "rcon.password", "passwd", "token",
                                  "api_key", "apikey", "api key", "discord_webhook", "Authorization:", "Bearer abc",
                                  "pass=abc", "rcon.pass abc", "pwd=abc", "key: abc", "store key abc", "storeKey=abc",
                                  "tebex", "credentials"])
def test_a_line_that_mentions_a_secret_is_left_out_whole(box, word):
    log(box, START + f"[10:01:00] [Server thread/ERROR]: Failed with {word} and more\n")
    assert [row["text"] for row in problems(box)["errors"]] == [staff_status.LEFT_OUT]
    assert word not in json.dumps(json.loads(box.out.read_text())["problems"])


@pytest.mark.parametrize("said", ["Bad ResourceKey[minecraft:made_up]", "Could not bypass the check", "Monkey escaped"])
def test_a_word_that_only_looks_like_a_secret_stays(box, said):
    log(box, START + f"[10:01:00] [Server thread/ERROR]: {said}\n")
    assert [row["text"] for row in problems(box)["errors"]] == [said]


@pytest.mark.parametrize("said, shown", [
    ("Lost /203.0.113.7:51234 today", "Lost /an address today"),
    ("Lost 203.0.113.7 today", "Lost an address today"),
    ("Lost /[2001:db8::1]:51234 today", "Lost /an address today"),
    ("Lost 2001:db8:0:0:0:0:0:1 today", "Lost an address today"),
    ("Lost fe80::1 today", "Lost an address today"),
    ("Fetching https://example.com/a?b=c failed", "Fetching <link> failed"),
    ("Number " + SEED + " failed", "Number <number> failed"),
    ("Bad\tcontrol\x1b[0m text", "Bad control [0m text"),
    ("made:up::thing kept 12:30:15", "made:up::thing kept 12:30:15"),
    ("x" * 200, "x" * 157 + "..."),
])
def test_what_a_line_shows(said, shown):
    assert staff_status.plain(said) == shown


def test_a_flood_is_read_a_piece_at_a_time_and_nothing_is_lost(box, monkeypatch):
    monkeypatch.setattr(staff_status, "LOG_READ", 200)
    lines = "".join("[10:01:00] [Server thread/ERROR]: Error sending packet\n" for _ in range(10))
    log(box, START + lines)
    counts = [sum(row["count"] for row in problems(box)["errors"]) for _ in range(6)]
    assert counts[-1] == 10 and counts[0] < 10


def test_a_line_longer_than_a_reading_is_stepped_over(box, monkeypatch):
    log(box, START)
    problems(box)
    monkeypatch.setattr(staff_status, "LOG_READ", 100)
    log(box, "x" * 250 + "\n[10:01:00] [Server thread/ERROR]: Error sending packet\n", "a")
    for _ in range(3):
        problems(box)
    assert [row["text"] for row in problems(box)["errors"]] == ["Error sending packet"]


def test_a_log_that_cannot_be_read_says_so_and_keeps_what_was_found(box):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    problems(box)
    path = box.live / "server" / "logs" / "latest.log"
    path.unlink()
    found = problems(box)
    assert found["read"] is False and found["errors"][0]["count"] == 1 and found["log"]["up"] is True
    path.mkdir()
    assert problems(box)["read"] is False


def test_no_log_is_no_reading_rather_than_good_news(box):
    found = problems(box)
    assert found["read"] is False and found["errors"] == [] and found["log"] is None


@pytest.mark.parametrize("old", [3, [], {"errors": 3, "lag": "x", "log": 5, "read": "y"},
                                 {"errors": [3, {"text": 1}, {"text": "x", "count": "y", "first": "", "last": "z"}],
                                  "lag": {"worst": "x"}, "log": {"size": "x", "head": 3}},
                                 {"log": {"size": -5, "head": "x", "up": "yes", "startup": "many"}}])
def test_an_unreadable_earlier_reading_starts_afresh(box, old):
    log(box, START + "[10:01:00] [Server thread/ERROR]: Error sending packet\n")
    box.out.write_text(json.dumps({"problems": old}))
    found = problems(box)
    assert [row["count"] for row in found["errors"]] == [1] and found["lag"] is None and found["log"]["up"] is True


def test_a_crash_report_gives_its_description_and_nothing_else(box):
    crash(box, "crash-new.txt", 1, f"---- Minecraft Crash Report ----\n// A joke\n\nTime: today\n"
                                   f"Description: Exception in server tick loop\r\n\nlevel-seed {SEED}\nmade.up\n")
    found = problems(box)
    assert found["crashes"] == [{"when": iso(NOW - dt.timedelta(hours=1)),
                                 "text": "Exception in server tick loop"}]
    assert SEED not in json.dumps(found) and "made.up" not in json.dumps(found)


def test_the_newest_five_crashes_of_the_day_are_listed(box):
    for n in range(7):
        crash(box, f"crash-{n}.txt", n + 1, f"Description: Number {n}\n")
    crash(box, "crash-old.txt", 25, "Description: Too old\n")
    crash(box, "notes.md", 0, "Description: Not a report\n")
    assert [row["text"] for row in problems(box)["crashes"]] == [f"Number {n}" for n in range(5)]


def test_an_old_crash_alone_is_nothing_to_report(box):
    crash(box, "crash-old.txt", 25, "Description: Too old\n")
    assert problems(box)["crashes"] == []


def test_a_crash_report_without_a_description_or_with_a_secret_in_it(box):
    crash(box, "crash-1.txt", 1, "Nothing useful\n")
    crash(box, "crash-2.txt", 2, f"Description: Bad seed {SEED}\n")
    assert [row["text"] for row in problems(box)["crashes"]] == [None, staff_status.LEFT_OUT]


def test_a_crash_folder_that_cannot_be_read_is_no_reading(box, monkeypatch):
    def refused(_):
        raise PermissionError("no")
    monkeypatch.setattr(staff_status.os, "scandir", refused)
    assert staff_status.recent_crashes(box.live / "server" / "crash-reports", 0) is None


def test_a_crash_report_removed_mid_scan_does_not_hide_the_others(box, monkeypatch):
    crash(box, "crash-1.txt", 1, "Description: Still here\n")
    folder = box.live / "server" / "crash-reports"
    real = list(os.scandir(folder))

    def gone():
        raise FileNotFoundError("removed")
    monkeypatch.setattr(staff_status.os, "scandir",
                        lambda _: [SimpleNamespace(name="crash-0.txt", path="crash-0.txt", stat=gone), *real])
    assert [row["text"] for row in staff_status.recent_crashes(folder, 0)] == ["Still here"]


def test_the_log_reader_keeps_no_log_text_and_a_full_day_stays_small(box):
    many = "".join(f"[10:01:00] [Server thread/ERROR]: {chr(97 + n)}{chr(97 + n // 26)} {'q' * 200}\n"
                   for n in range(60))
    log(box, START + many)
    found = problems(box)
    assert "Loading" not in json.dumps(found["log"])
    assert len(found["errors"]) == staff_status.ERRORS_KEPT
    assert len(json.dumps(found, separators=(",", ":"))) < 10_000


def test_the_last_backup_is_the_newest_named_copy_at_its_folder_time(box):
    assert read(box)["backups"]["local"] == "2026-11-15T01:00:00Z"
    shutil.rmtree(box.live / "backups")
    assert read(box)["backups"]["local"] is None


def test_the_off_site_copy_only_needs_the_files_to_exist(box):
    assert read(box)["backups"]["offsite"] == "not set up"
    box.settings.write_text("")
    assert read(box)["backups"]["offsite"] == "on"
    box.failing.write_text("")
    assert read(box)["backups"]["offsite"] == "failing"


def test_no_meminfo_is_no_numbers_not_a_crash(tmp_path):
    assert staff_status.memory(tmp_path / "missing") == (None, None)
    (tmp_path / "short").write_text("MemTotal:  1 kB\n")
    assert staff_status.memory(tmp_path / "short") == (None, None)


def test_write_replaces_the_file_whole_and_show_changes_nothing(box, monkeypatch, capsys):
    server = docker()
    monkeypatch.setattr(staff_status.server, "Docker", lambda _folder: server)
    assert staff_status.main(["show", str(box.live), "--at", "2026-11-15T02:00:00Z"]) == 0
    assert json.loads(capsys.readouterr().out)["online"] is True and not box.out.exists()
    for at in ("2026-11-15T02:00:00Z", "2026-11-15T02:02:00Z"):
        assert staff_status.main(["write", str(box.live), "--out", str(box.out), "--at", at]) == 0
    assert "online, 3 player count, 2 readings" in capsys.readouterr().out
    assert len(json.loads(box.out.read_text())["history"]) == 2
    assert [p.name for p in box.out.parent.glob(".status-*")] == []


@pytest.mark.parametrize("name", [*UNITS, "monkey-staff.sh", "Caddyfile.staff", "Caddyfile.staff-login"])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_units_run_the_script_as_monkey_every_two_minutes():
    service = (DEPLOY / "monkey-staff.service").read_text()
    assert "User=monkey" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-staff.sh\n" in service
    assert "Nice=10" in service
    assert "OnCalendar=*-*-* *:00/2:45\n" in (DEPLOY / "monkey-staff.timer").read_text()


def test_the_script_is_posix_sh_and_reads_no_secret():
    text = (DEPLOY / "monkey-staff.sh").read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert '. "$ENV_FILE"' not in text and "rcon.password" not in text and "WEBHOOK" not in text
    assert "deploy_lock" not in text
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR", "STAFF_DIR"}
    # A password on a command line shows in `ps`.
    assert "--plaintext" not in text
    for unit in UNITS:
        assert unit in text
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / "monkey-staff.sh")], check=True)


def test_the_password_only_guards_a_page_that_loads_nothing_from_elsewhere():
    caddy = (DEPLOY / "Caddyfile.staff").read_text()
    assert caddy.count("staff.monkeysmp.lscaturchio.xyz {") == 1
    assert "basic_auth bcrypt" in caddy and "import /etc/caddy/staff-logins" in caddy
    # The password comes before anything is served, in one route order Caddy can't rearrange.
    assert caddy.index("basic_auth") < caddy.index("handle /staff.json")
    assert "default-src 'none'" in caddy and "script-src 'self'" in caddy and "frame-ancestors 'none'" in caddy
    assert "X-Robots-Tag" in caddy and "no-store" in caddy
    # Whatever is served from the checkout is only the page and the fonts, never the checkout.
    roots = re.findall(r"root \* (\S+)", caddy)
    assert roots == ["/srv/monkey/staff", "/srv/monkey/repo/site/public", "/srv/monkey/repo/deploy/staff"]


def test_the_main_caddyfile_only_imports_the_staff_site_if_it_is_there():
    assert (DEPLOY / "Caddyfile").read_text().rstrip().endswith("import /etc/caddy/staff*.caddy")


def test_the_page_runs_under_the_strict_policy():
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html) and not re.search(r"<style\b", html)
    assert not re.search(r"\sstyle=|\son\w+=", html)
    assert not re.search(r"https?://", html)
    assert re.search(r'<meta name="robots" content="noindex', html)
    script = (PAGE / "staff.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "eval(" not in script and "document.write" not in script
    assert not re.search(r"https?://(?!www\.w3\.org/)", script)
    # A style attribute set from code is what the policy refuses.
    assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style", script)
    style = (PAGE / "staff.css").read_text(encoding="utf-8")
    assert not re.search(r"https?://", style.replace("http://www.w3.org/2000/svg", ""))


FAKES = {
    "id": 'echo "${FAKE_ID:-0}"',
    "python3": "echo FAKEPASSWORD",
    "sleep": 'echo "sleep $*" >>"$FAKE_CALLS"',
    "systemctl": 'echo "systemctl $*" >>"$FAKE_CALLS"',
    # FAKE_NO_READ is a path the caddy user can't read.
    "runuser": 'while [ "$1" != -- ]; do shift; done\nshift\n'
               'case "$*" in *"${FAKE_NO_READ:-@nothing@}"*) exit 1 ;; esac\nexec "$@"',
    # What a visit with no password gets: FAKE_DATA for the status file, FAKE_CODE for the rest.
    "curl": 'case "$*" in\n  *staff.json*) printf %s "${FAKE_DATA:-${FAKE_CODE:-401}}" ;;\n'
            '  *) printf %s "${FAKE_CODE:-401}" ;;\nesac',
    "caddy": 'echo "caddy $*" >>"$FAKE_CALLS"\ncase $1 in\n'
             '  hash-password) cat >"$FAKE_CALLS.stdin"; echo "\\$2a\\$08\\$fakehash" ;;\n'
             '  validate) exit "${FAKE_RC_validate:-0}" ;;\nesac',
    # Every install here is `install -d ... DIR` or `install -m M -o O -g G FROM TO`. Nothing goes to the real units.
    "install": 'echo "install $*" >>"$FAKE_CALLS"\n'
               'case $1 in -d) for last in "$@"; do :; done; mkdir -p "$last"; exit 0 ;; esac\n'
               "shift 6\n"
               'case $2 in /etc/systemd/*) ;; *) cp "$1" "$2" ;; esac',
}


@pytest.fixture
def staff(tmp_path):
    """Runs the real monkey-staff.sh under dash, as root unless asked, with what needs root or a real Caddy faked."""
    shell = shutil.which("dash")
    if not shell:
        pytest.skip("needs dash")
    bin_dir, caddy, calls = tmp_path / "bin", tmp_path / "caddy", tmp_path / "calls"
    bin_dir.mkdir()
    caddy.mkdir()
    for name, body in FAKES.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n", newline="\n")
        (bin_dir / name).chmod(0o755)
    (caddy / "Caddyfile").write_text("map.example.com {\n\trespond map\n}\n", newline="\n")

    def run(*args, **env):
        calls.unlink(missing_ok=True)
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "MONKEY_DEPLOY_ENV": (tmp_path / "none").as_posix(), "REPO_DIR": REPO.root.as_posix(),
                   "LIVE_DIR": "/srv/live", "STAFF_DIR": (tmp_path / "staff").as_posix(),
                   "CADDY_DIR": caddy.as_posix(), **env}
        done = subprocess.run([shell, (DEPLOY / "monkey-staff.sh").as_posix(), *args], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return SimpleNamespace(code=done.returncode, out=done.stdout,
                               calls=calls.read_text().splitlines() if calls.exists() else [])
    return SimpleNamespace(run=run, logins=caddy / "staff-logins", site=caddy / "staff.caddy",
                           main=caddy / "Caddyfile", stdin=tmp_path / "calls.stdin", folder=caddy)


RELOAD = "systemctl reload caddy"
IMPORT = "import /etc/caddy/staff*.caddy"


def test_the_site_never_goes_in_without_a_login(staff):
    before = staff.main.read_text()
    done = staff.run("--install")
    assert done.code == 1 and "no logins yet" in done.out
    assert not staff.site.exists() and staff.main.read_text() == before
    assert not [line for line in done.calls if line.startswith("systemctl")]


def test_a_login_keeps_only_a_hash_and_shows_the_password_once(staff):
    done = staff.run("--login", "diego")
    assert done.code == 0
    assert done.out.count("FAKEPASSWORD") == 1 and "password: FAKEPASSWORD\n" in done.out
    assert staff.logins.read_text() == "diego $2a$08$fakehash\n"
    # On stdin with its newline: never on a command line, where `ps` would show it.
    assert staff.stdin.read_text() == "FAKEPASSWORD\n" and "FAKEPASSWORD" not in "\n".join(done.calls)
    assert "caddy hash-password --algorithm bcrypt --bcrypt-cost 8" in done.calls
    assert any(line.startswith("install -m 640 -o root -g caddy ") for line in done.calls)
    # No site yet, so nothing to reload, and the temporary copies are gone.
    assert RELOAD not in done.calls
    assert [p.name for p in staff.folder.iterdir() if p.name.startswith(".")] == []


def test_a_new_password_replaces_the_old_and_other_names_stay(staff):
    staff.run("--login", "diego")
    staff.run("--login", "owner")
    staff.run("--login", "diego")
    assert sorted(staff.logins.read_text().splitlines()) == ["diego $2a$08$fakehash", "owner $2a$08$fakehash"]


@pytest.mark.parametrize("args", [("--login",), ("--login", "two words"), ("--login", "a/b"), ("--login", "a:b"),
                                  ("--remove-login",), ("--nonsense",)])
def test_a_bad_name_or_mode_changes_nothing(staff, args):
    assert staff.run(*args).code == 2
    assert not staff.logins.exists()


@pytest.mark.parametrize("mode", [("--login", "diego"), ("--remove-login", "diego"), ("--install",)])
def test_changing_caddy_takes_root(staff, mode):
    done = staff.run(*mode, FAKE_ID="1000")
    assert done.code == 1 and "run as root" in done.out and not staff.logins.exists()


def test_install_adds_the_import_once_and_keeps_the_rest_of_the_live_file(staff):
    before = staff.main.read_text()
    staff.run("--login", "diego")
    first, second = staff.run("--install"), staff.run("--install")
    for done in (first, second):
        assert done.code == 0 and "refused (401)" in done.out and RELOAD in done.calls
    after = staff.main.read_text()
    assert after.startswith(before) and after.splitlines().count(IMPORT) == 1
    assert staff.site.read_text() == (DEPLOY / "Caddyfile.staff").read_text()
    assert "systemctl enable --now monkey-staff.timer" in first.calls
    assert [p.name for p in staff.folder.iterdir() if p.name.startswith(".")] == []


@pytest.mark.parametrize("page, data", [("200", "200"), ("401", "200"), ("200", "401"), ("403", "403"), ("502", "502"),
                                        ("401", "000")])
def test_a_visit_that_is_not_refused_takes_the_site_back_out(staff, page, data):
    staff.run("--login", "diego")
    done = staff.run("--install", FAKE_CODE=page, FAKE_DATA=data)
    assert done.code == 1 and "out of Caddy again" in done.out
    assert not staff.site.exists() and done.calls.count(RELOAD) == 2
    assert "systemctl enable --now monkey-staff.timer" not in done.calls


@pytest.mark.parametrize("path", ["deploy/staff", "site/public/fonts", "staff"])
def test_a_page_caddy_cannot_read_never_goes_in(staff, path):
    staff.run("--login", "diego")
    before = staff.main.read_text()
    done = staff.run("--install", FAKE_NO_READ=path)
    assert done.code == 1 and "caddy user can't read" in done.out
    assert not staff.site.exists() and staff.main.read_text() == before
    assert RELOAD not in done.calls and "systemctl enable --now monkey-staff.timer" not in done.calls


def test_no_answer_yet_waits_for_the_certificate_then_says_why(staff):
    staff.run("--login", "diego")
    done = staff.run("--install", FAKE_CODE="000")
    assert done.code == 0 and "DNS record" in done.out and staff.site.exists()
    assert done.calls.count("sleep 5") == 12


def test_caddy_refusing_the_site_puts_everything_back(staff):
    staff.run("--login", "diego")
    before = staff.main.read_text()
    done = staff.run("--install", FAKE_RC_validate="1")
    assert done.code == 1 and "caddy refused" in done.out
    assert staff.main.read_text() == before and not staff.site.exists() and RELOAD not in done.calls
    assert "systemctl enable --now monkey-staff.timer" not in done.calls
    # The same over a site that is already in: the old one comes back rather than none.
    assert staff.run("--install").code == 0
    installed = staff.main.read_text()
    staff.site.write_text("the old site\n", newline="\n")
    assert staff.run("--install", FAKE_RC_validate="1").code == 1
    assert staff.site.read_text() == "the old site\n" and staff.main.read_text() == installed


def test_caddy_refusing_new_logins_keeps_the_old_ones_and_shows_no_password(staff):
    staff.run("--login", "diego")
    staff.run("--install")
    before = staff.logins.read_text()
    done = staff.run("--login", "owner", FAKE_RC_validate="1")
    assert done.code == 1 and "FAKEPASSWORD" not in done.out and staff.logins.read_text() == before
    assert RELOAD not in done.calls


def test_logins_change_at_once_on_a_running_site(staff):
    staff.run("--login", "diego")
    staff.run("--install")
    assert RELOAD in staff.run("--login", "owner").calls
    done = staff.run("--remove-login", "owner")
    assert done.code == 0 and RELOAD in done.calls
    assert staff.logins.read_text() == "diego $2a$08$fakehash\n"


def test_the_last_login_stays_while_the_site_is_up(staff):
    staff.run("--login", "diego")
    staff.run("--install")
    done = staff.run("--remove-login", "diego")
    assert done.code == 1 and "last login" in done.out and staff.logins.read_text() == "diego $2a$08$fakehash\n"
    staff.site.unlink()
    assert staff.run("--remove-login", "diego").code == 0 and staff.logins.read_text() == ""


def test_removing_a_login_that_is_not_there_says_so(staff):
    staff.run("--login", "diego")
    done = staff.run("--remove-login", "nobody")
    assert done.code == 1 and "no login called nobody" in done.out
    assert staff.logins.read_text() == "diego $2a$08$fakehash\n"


def test_check_names_the_logins_without_their_hashes_and_changes_nothing(staff):
    staff.run("--login", "diego")
    staff.run("--install")
    before = staff.logins.read_text(), staff.main.read_text()
    done = staff.run("--check")
    assert done.code == 0 and "logins: diego\n" in done.out and "gets: 401" in done.out
    assert "$2a$" not in done.out and "check finished: nothing was changed" in done.out
    assert (staff.logins.read_text(), staff.main.read_text()) == before and RELOAD not in done.calls
    assert "caddy user can read" in done.out and "PROBLEM" not in done.out
    done = staff.run("--check", FAKE_NO_READ="deploy/staff")
    assert done.code == 0 and "PROBLEM: the caddy user can't read" in done.out


def test_the_status_job_refuses_root_and_needs_its_folder(staff):
    done = staff.run()
    assert done.code == 1 and "run it as monkey" in done.out
    done = staff.run(FAKE_ID="1000")
    assert done.code == 1 and "--install" in done.out
