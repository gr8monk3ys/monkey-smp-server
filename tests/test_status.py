import datetime as dt
import json
import re
import shutil
import subprocess

import pytest
import status
from fake_world import FakeWorld

import rcon
import season_calendar
from repo import REPO

DEPLOY = REPO.root / "deploy"
OVERWORLD = "minecraft:overworld"
LIST = "There are 3 of a max of 30 players online: Alpha, Bravo, Charlie"
UTC = dt.timezone.utc   # noqa: UP017 (as the tools: datetime.UTC is 3.11+)


def at(text: str) -> dt.datetime:
    return rcon.parse_time(text)


def world(tmp_path, size=2500.0, target=None):
    return FakeWorld(tmp_path / "world").border(OVERWORLD, -80.0, 416.0, size, target).path


def season_one_rows() -> dict[int, str]:
    """docs/SEASONS.md's "Season I calendar" table: week -> its event cell."""
    text = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8")
    table = text[text.index("#### Season I calendar"):]
    rows = {}
    for line in table.splitlines():
        m = re.match(r"\| (\d+) \| [^|]+\| ([^|]+)\|", line)
        if m:
            rows.setdefault(int(m[1]), m[2])
    return rows


def test_the_schedule_is_the_season_one_table_in_seasons_md():
    rows = season_one_rows()
    assert [week for week, _, _ in status.SCHEDULE] == list(range(status.LAST_WEEK + 1))
    for week, what, size in status.SCHEDULE[1:]:
        assert what in rows[week], (week, what, rows[week])
        assert (f"to {size}" in rows[week]) if size else ("border breaks" not in rows[week])
    assert "Launch" in rows[0]


def test_the_dates_follow_the_calendar():
    dates = status.dates()
    assert dates[0] == (season_calendar.LAUNCH, "Season I opens", None)
    raid = next(when for when, what, _ in dates if what == "Faction Raid I")
    assert raid == dt.datetime(2026, 11, 14, 18, tzinfo=season_calendar.PACIFIC)
    closes = [when for when, what, _ in dates if what == status.CLOSE]
    assert len(closes) == status.LAST_WEEK
    assert closes[0] == dt.datetime(2026, 11, 15, 19, tzinfo=season_calendar.PACIFIC)
    assert all(when.astimezone(season_calendar.PACIFIC).weekday() == 6 for when in closes)
    assert [w for w, _, _ in dates] == sorted(w for w, _, _ in dates)


def test_the_phases():
    assert status.phase(at("2026-11-08T00:59:59Z")) == "preseason"
    assert status.phase(at("2026-11-08T01:00:00Z")) == "live"
    assert status.phase(at("2027-01-25T07:59:00Z")) == "live"         # Sunday 24 Jan, 11:59 PM Pacific
    assert status.phase(at("2027-01-25T08:00:00Z")) == "offseason"    # week 12


def test_only_the_count_is_read_from_list():
    assert status.players(LIST) == 3
    assert status.players("There are 0 of a max of 30 players online: ") == 0
    assert status.players("nothing useful") is None


def test_a_live_season_shows_the_count_the_next_event_and_the_border(tmp_path):
    server = rcon.Recorder({"list": LIST})
    data = status.status(world(tmp_path), at("2026-11-12T03:00:00Z"), server)
    assert data == {
        "version": 1, "checked": "2026-11-12T03:00:00Z", "season": 1, "phase": "live",
        "opens": "2026-11-08T01:00:00Z", "online": True, "players": 3,
        "next": {"what": "Faction Raid I", "at": "2026-11-15T02:00:00Z"},
        "border": {"size": 2500, "growing_to": None, "next": {"size": 4000, "at": "2026-11-22T02:00:00Z"}},
    }
    assert server.sent == ["list"]


def test_the_file_never_holds_a_name(tmp_path):
    out = tmp_path / "status" / "status.json"
    status.write(out, status.status(world(tmp_path), at("2026-11-12T03:00:00Z"), rcon.Recorder({"list": LIST})))
    text = out.read_text(encoding="utf-8")
    assert not any(name in text for name in ("Alpha", "Bravo", "Charlie"))
    assert json.loads(text)["players"] == 3 and text.endswith("\n")
    assert [p.name for p in out.parent.iterdir()] == ["status.json"]   # no temporary file left behind


def test_before_the_launch_there_is_no_count(tmp_path):
    data = status.status(world(tmp_path), at("2026-11-01T20:00:00Z"), rcon.Recorder({"list": LIST}))
    assert data["phase"] == "preseason" and data["online"] is True and data["players"] is None
    assert data["next"] == {"what": "Season I opens", "at": "2026-11-08T01:00:00Z"}


def test_a_stopped_or_silent_server_is_offline(tmp_path):
    folder = world(tmp_path)
    when = at("2026-11-12T03:00:00Z")
    for server in (rcon.Recorder(running=False), rcon.Recorder({"list": LIST}, fail=1), None):
        data = status.status(folder, when, server)
        assert data["online"] is False and data["players"] is None


def test_a_growing_border_and_the_act_after_it(tmp_path):
    data = status.status(world(tmp_path, 3000.0, 4000.0), at("2026-11-22T02:05:00Z"))
    assert data["border"] == {"size": 3000, "growing_to": 4000, "next": {"size": 6000, "at": "2026-12-27T02:00:00Z"}}
    # A border grown by hand past the next act: no act makes it bigger.
    data = status.status(world(tmp_path, 6000.0), at("2026-11-12T03:00:00Z"))
    assert data["border"]["next"] is None


def test_no_border_saved_and_a_damaged_one(tmp_path):
    (tmp_path / "empty").mkdir()
    assert status.status(tmp_path / "empty", at("2026-11-12T03:00:00Z"))["border"] is None
    folder = world(tmp_path)
    next(folder.rglob("world_border.dat")).write_bytes(b"\x1f\x8b broken")
    assert status.status(folder, at("2026-11-12T03:00:00Z"))["border"] is None


def test_after_the_season_nothing_is_next(tmp_path):
    data = status.status(world(tmp_path), at("2027-02-01T00:00:00Z"), rcon.Recorder({"list": LIST}))
    assert data["phase"] == "offseason" and data["next"] is None and data["players"] is None


def test_show_and_schedule_print(tmp_path, capsys):
    assert status.main(["show", str(world(tmp_path)), "--at", "2026-11-12T03:00:00Z"]) == 0
    assert json.loads(capsys.readouterr().out)["online"] is False
    assert status.main(["schedule"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Sat 7 Nov, 5 PM Pacific: Season I opens"
    assert "Sat 21 Nov, 6 PM Pacific: The border breaks (to 4000)" in out


UNITS = ["monkey-status.service", "monkey-status.timer"]


@pytest.mark.parametrize("name", ["monkey-status.sh", "Caddyfile", *UNITS])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_posix_sh_reads_no_secret_and_takes_no_lock():
    text = (DEPLOY / "monkey-status.sh").read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert '. "$ENV_FILE"' not in text and "rcon.password" not in text and "WEBHOOK" not in text
    assert "deploy_lock" not in text
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR", "STATUS_DIR"}
    for unit in UNITS:
        assert unit in text
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / "monkey-status.sh")], check=True)


def test_units_run_the_script_as_monkey_every_two_minutes():
    service = (DEPLOY / "monkey-status.service").read_text()
    assert "User=monkey" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-status.sh\n" in service
    assert "OnCalendar=*-*-* *:00/2:15\n" in (DEPLOY / "monkey-status.timer").read_text()


def test_caddy_serves_the_status_beside_the_map_with_cors_and_a_short_cache():
    caddy = (DEPLOY / "Caddyfile").read_text()
    assert caddy.count("map.monkeysmp.lscaturchio.xyz {") == 1 and "reverse_proxy 127.0.0.1:8100" in caddy
    block = caddy[caddy.index("handle /status.json {"):]
    block = block[:block.index("\n\t}")]
    assert "root * /srv/monkey/status" in block and "file_server" in block
    assert 'Access-Control-Allow-Origin "*"' in block and 'Cache-Control "public, max-age=60"' in block
    # The website reads it from the same address the map has (site/config.json).
    config = json.loads((REPO.root / "site" / "config.json").read_text(encoding="utf-8"))
    assert config["STATUS_URL"] == config["MAP_URL"] + "/status.json"
