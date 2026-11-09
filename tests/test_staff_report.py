"""The staff page's weekly rule check: tools/staff_report.py, its panel routes, deploy/monkey-report.* and the Reports
tab (deploy/staff/reports.js). A made-up world: a tiny Ledger database, stats, parties, usercache and logs."""
import datetime as dt
import gzip
import json
import os
import re
import sqlite3

import pytest
import staff_report
from nbt_writer import Ints, nbt
from test_staff_panel import box  # noqa: F401 (the fixture: the real panel over HTTP)

from repo import REPO

DEPLOY = REPO.root / "deploy"
PAGE = DEPLOY / "staff"
PACIFIC = staff_report.calendar.PACIFIC
NOW = dt.datetime(2026, 11, 17, 9, 0, tzinfo=dt.UTC)     # Monday after W46, 1 AM Pacific
WEEK = "2026-W46"                                                  # Mon 9 Nov to Mon 16 Nov 2026

ACTIONS = ["block-place", "block-change", "block-break", "item-remove", "item-pick-up", "item-drop", "item-insert",
           "entity-kill", "entity-change", "entity-mount", "entity-dismount"]
SOURCES = ["command", "gravity", "tnt", "explosion", "creeper", "fire", "player"]
WORLDS = ["minecraft:overworld", "minecraft:the_end", "minecraft:the_nether"]
PLAYERS = {"Alpha": "2026-11-01 10:00:00", "Bravo": "2026-11-01 10:00:00", "Carol": "2026-11-01 10:00:00",
           "Dan": "2026-11-09 20:00:00", "Eve": "2026-11-01 10:00:00"}
UUID = {name: f"0000000{i}-0000-0000-0000-00000000000{i}" for i, name in enumerate(PLAYERS, 1)}


def ledger(path, rows):
    """Ledger's tables and indexes as the live database has them, with `rows`:
    (time, action, x, y, z, world, object, old_object, source, player, extra)."""
    db = sqlite3.connect(path)
    db.executescript("""
        create table ActionIdentifiers (id integer primary key, action_identifier text unique);
        create table ObjectIdentifiers (id integer primary key, identifier text unique);
        create table sources (id integer primary key, name text unique);
        create table worlds (id integer primary key, identifier text unique);
        create table players (id integer primary key, player_id blob unique, player_name text, first_join text,
                              last_join text);
        create table actions (id integer primary key, action_id int, time text, x int, y int, z int, world_id int,
                              object_id int, old_object_id int, block_state text, old_block_state text, source int,
                              player_id int, extra_data text, rolled_back int default 0);
        create index actions_action_id on actions (action_id);
        create index actions_time on actions (time);
        create index actions_object_id on actions (object_id);
        create index actions_old_object_id on actions (old_object_id);
        create index actions_source on actions (source);
        create index actions_player_id on actions (player_id);
        create index actions_by_location on actions (x, y, z, world_id);
    """)
    db.executemany("insert into ActionIdentifiers values (?, ?)", enumerate(ACTIONS, 1))
    db.executemany("insert into sources values (?, ?)", enumerate(SOURCES, 1))
    db.executemany("insert into worlds values (?, ?)", enumerate(WORLDS, 1))
    for i, (name, first) in enumerate(PLAYERS.items(), 1):
        db.execute("insert into players values (?, ?, ?, ?, ?)", (i, bytes([i] * 16), name, first, first))
    objects: dict[str, int] = {}

    def obj(name):
        if name is None:
            return None
        if name not in objects:
            objects[name] = len(objects) + 1
            db.execute("insert into ObjectIdentifiers values (?, ?)", (objects[name], f"minecraft:{name}"))
        return objects[name]

    ids = {name: i for i, name in enumerate(PLAYERS, 1)}
    for t, action, x, y, z, world, o, oo, source, player, extra in rows:
        db.execute("insert into actions (action_id, time, x, y, z, world_id, object_id, old_object_id, source, "
                   "player_id, extra_data) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (ACTIONS.index(action) + 1, f"{t}.000", x, y, z, WORLDS.index(f"minecraft:{world}") + 1, obj(o),
                    obj(oo), SOURCES.index(source) + 1, ids.get(player), extra))
    db.commit()
    db.close()


def place(t, who, block, x, y, z, world="overworld"):
    return (t, "block-place", x, y, z, world, block, "air", "player", who, None)


def brk(t, who, block, x, y, z, world="overworld", source="player"):
    return (t, "block-break", x, y, z, world, "air", block, source, who, None)


def take(t, who, x, y, z, item="diamond", n=1):
    return (t, "item-remove", x, y, z, "overworld", item, None, "player", who, f'{{count:{n},id:"minecraft:{item}"}}')


def put(t, who, x, y, z, item="cobblestone"):
    return (t, "item-insert", x, y, z, "overworld", item, None, "player", who, f'{{count:1,id:"minecraft:{item}"}}')


def week_rows():
    rows = [
        # A portal Alpha broke and caged; Bravo added netherrack to it.
        brk("2026-11-10 10:00:00", "Alpha", "nether_portal", 100, 64, 100),
        brk("2026-11-10 10:00:00", "Alpha", "nether_portal", 100, 65, 101),
        place("2026-11-10 10:01:00", "Alpha", "obsidian", 100, 64, 100),
        place("2026-11-10 10:00:30", "Bravo", "netherrack", 101, 66, 101),
        # A portal that collapsed by itself (gravity, no player), caged by Carol.
        brk("2026-11-10 11:00:00", None, "nether_portal", 500, 70, 500, source="gravity"),
        place("2026-11-10 11:00:20", "Carol", "obsidian", 500, 70, 501),
        # Bedrock, TNT at spawn and far away, the Nether roof.
        brk("2026-11-11 09:00:00", "Dan", "bedrock", 0, -60, 0),
        place("2026-11-11 09:05:00", "Eve", "tnt", 10, 64, 10),
        place("2026-11-11 09:06:00", "Eve", "tnt", 1000, 64, 1000),
        place("2026-11-11 09:07:00", "Dan", "netherrack", 0, 130, 0, world="the_nether"),
        # Dynamic Lights' rows (source command) never count, even with a player on them.
        brk("2026-11-11 10:00:00", "Alpha", "bedrock", 5, -60, 5, source="command"),
        ("2026-11-11 10:00:01", "block-place", 5, 64, 5, "overworld", "light", "air", "command", None, None),
        # Carol's chest, raided by Dan three times: one way, so likely theft.
        place("2026-11-09 08:00:00", "Carol", "chest", 200, 64, 200),
        *(take(f"2026-11-12 12:00:0{i}", "Dan", 200, 64, 200, "diamond", 4) for i in range(3)),
        # Alpha's ender chest and a teammate's take: neither counts.
        place("2026-11-09 08:00:00", "Alpha", "ender_chest", 300, 64, 300),
        take("2026-11-12 12:01:00", "Dan", 300, 64, 300),
        place("2026-11-09 08:00:00", "Alpha", "chest", 310, 64, 310),
        take("2026-11-12 12:02:00", "Bravo", 310, 64, 310),
        # Eve and Alpha use each other's chests: a shared base, not theft.
        place("2026-11-09 08:00:00", "Eve", "barrel", 320, 64, 320),
        take("2026-11-12 12:03:00", "Eve", 310, 64, 310),
        take("2026-11-12 12:04:00", "Alpha", 320, 64, 320),
        # Before the week: not this report's.
        brk("2026-11-08 09:00:00", "Eve", "bedrock", 9, -60, 9),
    ]
    # Mining: three players with 600 stone each, Carol finding far more diamond ore.
    for who, ores in (("Alpha", 1), ("Bravo", 1), ("Carol", 30)):
        rows += [brk(f"2026-11-13 10:{i // 60:02d}:{i % 60:02d}", who, "stone", i, 12, 0) for i in range(600)]
        rows += [brk(f"2026-11-13 11:00:{i:02d}", who, "deepslate_diamond_ore", i, -40, 0) for i in range(ores)]
    return rows


def stats(path, used=None, crafted=None, picked=None):
    data = {"stats": {"minecraft:used": {f"minecraft:{k}": v for k, v in (used or {}).items()},
                      "minecraft:crafted": {f"minecraft:{k}": v for k, v in (crafted or {}).items()},
                      "minecraft:picked_up": {f"minecraft:{k}": v for k, v in (picked or {}).items()}},
            "DataVersion": 4700}
    path.write_text(json.dumps(data), encoding="utf-8")


def log(path, lines, mtime=None):
    text = "".join(f"[{t}] [Server thread/INFO]: {line}\n" for t, line in lines)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(text.encode()))
    else:
        path.write_text(text, encoding="utf-8")
    if mtime:
        stamp = mtime.timestamp()
        os.utime(path, (stamp, stamp))


@pytest.fixture
def live(tmp_path):
    root = tmp_path / "made-up"
    server = root / "server"
    world = server / "world"
    (world / "players" / "stats").mkdir(parents=True)
    (world / "data" / "openpartiesandclaims" / "parties").mkdir(parents=True)
    (server / "logs").mkdir(parents=True)
    ledger(world / "ledger.sqlite", week_rows())
    (world / "level.dat").write_bytes(nbt({"Data": {"spawn": {"pos": Ints([0, 64, 0]),
                                                              "dimension": "minecraft:overworld"}}}, gzipped=True))
    parties = world / "data" / "openpartiesandclaims" / "parties"
    (parties / "a.nbt").write_bytes(nbt({"owner": {"uuid": Ints([0, 0, 0, 1]), "username": "Alpha"},
                                         "members": [{"uuid": Ints([0, 0, 0, 2]), "username": "Bravo"}]}))
    (parties / "c.nbt").write_bytes(nbt({"owner": {"uuid": Ints([0, 0, 0, 3]), "username": "Carol"}, "members": []}))
    (server / "usercache.json").write_text(json.dumps([{"uuid": u, "name": n, "expiresOn": "x"}
                                                       for n, u in UUID.items()]), encoding="utf-8")
    st = world / "players" / "stats"
    stats(st / f"{UUID['Alpha']}.json", used={"ender_pearl": 5}, crafted={"netherite_chestplate": 1},
          picked={"totem_of_undying": 1})
    stats(st / f"{UUID['Bravo']}.json", used={"enchanted_golden_apple": 2})
    stats(st / f"{UUID['Carol']}.json")
    logs = server / "logs"
    log(logs / "2026-11-10-1.log.gz", [
        ("12:00:00", "Alpha[/203.0.113.7:5555] logged in with entity id 5 at (0.5, 64.0, 0.5)"),
        ("12:00:05", "Bravo[/203.0.113.7:6666] logged in with entity id 6 at (0.5, 64.0, 0.5)"),
        ("12:00:10", "Carol[/198.51.100.9:1234] logged in with entity id 7 at (0.5, 64.0, 0.5)"),
        ("12:05:00", "<Dan> Eve was slain by Carol"),
        ("12:10:00", "Dan was slain by Carol"),
        ("12:20:00", "Eve lost connection: Timed out"),
        ("12:20:01", "Eve has died of cowardice"),
        ("23:59:59", "Bravo has died of cowardice"),
        ("00:00:05", "Carol was slain by Alpha using [Sword]"),     # the next day, 11 Nov
    ])
    log(logs / "latest.log", [("08:00:00", "Alpha has died of cowardice")],
        mtime=dt.datetime(2026, 11, 12, 8, 1, tzinfo=PACIFIC))
    return root


def report(live, week=WEEK, reports=None, now=NOW):
    out, snapshot = staff_report.make(live, week, reports, now)
    json.dumps(out)     # all of it is plain JSON
    return out, snapshot


def cells(out):
    return {p["name"]: p["cells"] for p in out["players"]}


def test_week_bounds_are_monday_to_monday_pacific():
    assert staff_report.week_bounds("2026-W46") == (dt.datetime(2026, 11, 9), dt.datetime(2026, 11, 16))
    assert staff_report.week_name(dt.date(2026, 11, 15)) == "2026-W46"
    with pytest.raises(ValueError):
        staff_report.week_bounds("2026-46")


def test_portal_trapping_by_who_broke_and_who_caged(live):
    c = cells(report(live)[0])
    assert c["Alpha"]["portal"]["level"] == "clear" and c["Alpha"]["portal"]["count"] == 1
    assert c["Bravo"]["portal"]["level"] == "unclear"
    assert "broken by Alpha" in c["Bravo"]["portal"]["evidence"][0]["what"]
    carol = c["Carol"]["portal"]
    assert carol["level"] == "likely" and "collapsed by itself" in carol["evidence"][0]["what"]
    assert carol["evidence"][0]["world"] == "Overworld" and carol["evidence"][0]["pos"] == [500, 70, 500]


def test_ledger_checks_leave_out_dynamic_lights_and_other_weeks(live):
    out = report(live)[0]
    c = cells(out)
    assert [e["pos"] for e in c["Dan"]["bedrock"]["evidence"]] == [[0, -60, 0]]
    assert "bedrock" not in c["Alpha"] and "Eve" not in [n for n, x in c.items() if "bedrock" in x]
    assert c["Eve"]["tnt"]["count"] == 1 and c["Eve"]["tnt"]["level"] == "likely"
    assert c["Dan"]["roof"]["evidence"][0]["world"] == "Nether"


def test_chest_takes_one_way_only_and_never_ender_chests_or_teammates(live):
    c = cells(report(live)[0])
    theft = c["Dan"]["theft"]
    assert theft["count"] == 3 and theft["level"] == "likely"
    assert theft["evidence"][0]["what"] == "took 4 diamond from Carol's chest"
    assert all("theft" not in c[n] for n in ("Alpha", "Bravo", "Eve"))


def test_stats_counts_and_pickups_are_unclear(live):
    out = report(live)[0]
    c = cells(out)
    assert c["Alpha"]["pearls"] == {**c["Alpha"]["pearls"], "count": 5, "level": "clear", "what": "thrown"}
    assert c["Alpha"]["netherite"]["level"] == "clear"
    assert c["Alpha"]["totems"]["level"] == "unclear" and c["Alpha"]["totems"]["what"] == "picked up"
    assert c["Bravo"]["gapples"]["count"] == 2
    assert any("first joined" in n for n in out["notes"])


def test_logs_kills_combat_logs_and_shared_connections(live):
    out = report(live)[0]
    c = cells(out)
    assert c["Carol"]["grace"]["level"] == "unclear" and c["Carol"]["grace"]["count"] == 1     # Dan, a day in
    assert "grace" not in c["Alpha"]                                   # Carol joined long before
    assert c["Eve"]["combatlog"]["level"] == "unclear"                  # timed out first: a network drop
    assert c["Bravo"]["combatlog"]["level"] == "clear"
    assert c["Bravo"]["combatlog"]["evidence"][0]["time"] == "2026-11-10 23:59:59"
    assert c["Alpha"]["combatlog"]["evidence"][0]["time"] == "2026-11-12 08:00:00"     # latest.log's day
    assert "Bravo" in c["Alpha"]["sharing"]["evidence"][0]["what"]
    assert "sharing" not in c["Carol"]
    assert "launch" not in [x["id"] for x in out["checks"]]           # not the launch week
    text = json.dumps(out)
    assert "203.0.113" not in text and "198.51.100" not in text      # never an address


def test_xray_outlier_and_the_clean_list(live):
    out = report(live)[0]
    c = cells(out)
    assert c["Carol"]["xray"]["level"] == "unclear" and "Alpha" not in [n for n, x in c.items() if "xray" in x]
    assert {r["name"] for r in out["mining"]} == {"Alpha", "Bravo", "Carol"}
    clean = {x["id"] for x in out["clean"]}
    assert {"crystals", "faction", "group"} <= clean
    assert "theft" not in clean and not out["skipped"]


def test_group_over_four_links_factions_both_ways(live):
    rows = week_rows()
    # Alpha+Bravo, Carol, Dan and Eve: Eve and Alpha share already; add Carol <-> Eve and Dan <-> Eve, 3 each way.
    rows += [place("2026-11-09 08:00:00", "Dan", "chest", 400, 64, 400)]
    for i in range(3):
        rows += [take(f"2026-11-14 10:00:0{i}", "Eve", 200, 64, 200),
                 take(f"2026-11-14 10:01:0{i}", "Carol", 320, 64, 320),
                 take(f"2026-11-14 10:02:0{i}", "Eve", 400, 64, 400),
                 take(f"2026-11-14 10:03:0{i}", "Dan", 320, 64, 320),
                 take(f"2026-11-14 10:04:0{i}", "Eve", 310, 64, 310),
                 take(f"2026-11-14 10:05:0{i}", "Alpha", 320, 64, 320)]
    path = live / "server" / "world" / "ledger.sqlite"
    path.unlink()
    ledger(path, rows)
    out = report(live)[0]
    c = cells(out)
    assert {n for n, x in c.items() if "group" in x} == {"Alpha", "Carol", "Dan", "Eve"}
    assert c["Eve"]["group"]["level"] == "unclear"
    assert any(n.startswith("Rule 32: 5 players") for n in out["notes"])


def test_the_launch_week_leaves_out_test_play_and_flags_the_launch_hour(live):
    logs = live / "server" / "logs"
    log(logs / "2026-11-07-1.log.gz", [
        ("16:00:00", "Dan has died of cowardice"),                     # before the launch: test play
        ("17:05:00", "Bravo was slain by Carol"),
        ("17:10:00", "Alpha was slain by Bravo"),                      # a teammate
        ("18:30:00", "Eve was slain by Dan"),                          # after the launch hour
    ])
    path = live / "server" / "world" / "ledger.sqlite"
    path.unlink()
    ledger(path, [brk("2026-11-06 09:00:00", "Dan", "bedrock", 0, -60, 0),
                  brk("2026-11-07 18:00:00", "Eve", "bedrock", 1, -60, 1)])
    out = report(live, "2026-W45", now=dt.datetime(2026, 11, 10, 9, tzinfo=dt.UTC))[0]
    c = cells(out)
    assert "launch" in [x["id"] for x in out["checks"]]
    assert c["Carol"]["launch"]["level"] == "likely" and "5 min" in c["Carol"]["launch"]["evidence"][0]["what"]
    assert c["Bravo"]["launch"]["level"] == "unclear"
    assert not {"launch", "combatlog", "bedrock"} & set(c.get("Dan", {}))
    assert c["Eve"]["bedrock"]["count"] == 1
    assert any("staff test play" in n for n in out["notes"])


def test_missing_sources_are_skipped_not_clean(tmp_path):
    (tmp_path / "server").mkdir()
    out = report(tmp_path)[0]
    skipped = {x["id"] for x in out["skipped"]}
    assert {"pearls", "portal", "theft", "faction", "combatlog"} <= skipped
    assert not skipped & {x["id"] for x in out["clean"]}
    assert out["players"] == []


def test_write_keeps_a_stats_copy_skips_a_written_week_and_counts_from_the_copy(live, tmp_path):
    out = tmp_path / "reports"
    said = staff_report.write(live, out, WEEK, NOW)
    assert "2026-W46.json" in said and (out / "2026-W46.json").is_file()
    copy = json.loads((out / "stats" / "2026-W46.json").read_text(encoding="utf-8"))
    assert copy["players"][UUID["Alpha"]]["used/ender_pearl"] == 5
    assert "skipped" in staff_report.write(live, out, WEEK, NOW)
    # The next week counts from the copy: 2 more pearls is 2, not 7.
    stats(live / "server" / "world" / "players" / "stats" / f"{UUID['Alpha']}.json", used={"ender_pearl": 7},
          crafted={"netherite_chestplate": 1}, picked={"totem_of_undying": 1})
    nxt = report(live, "2026-W47", out, dt.datetime(2026, 11, 24, 9, tzinfo=dt.UTC))[0]
    alpha = cells(nxt)["Alpha"]
    assert alpha["pearls"]["count"] == 2 and "netherite" not in alpha and "totems" not in alpha
    assert nxt["sources"]["stats"].endswith("2026-W46")


def test_show_prints_the_week_so_far_and_writes_nothing(live, capsys):
    before = sorted(p for p in live.rglob("*"))
    assert staff_report.main(["show", str(live), "--at", "2026-11-12T20:00:00Z"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["week"] == WEEK and out["partial"].startswith("the week so far")
    assert sorted(p for p in live.rglob("*")) == before


def test_the_database_is_opened_read_only(live):
    path = live / "server" / "world" / "ledger.sqlite"
    db = staff_report.Ledger(path)
    with pytest.raises(sqlite3.OperationalError):
        db.db.execute("delete from actions")


# ---------------------------------------------------------------- the panel routes


def test_routes_list_and_show_weeks_to_moderators(box, live):    # noqa: F811
    reports = box.staff / "reports"
    staff_report.write(live, reports, WEEK, NOW)
    (reports / "notes.json").write_text("{}", encoding="utf-8")       # not a week: left out
    status, data = box.call("GET", "/api/reports", role="moderator")
    assert status == 200 and [w["week"] for w in data["weeks"]] == [WEEK]
    assert data["weeks"][0]["players"] >= 5 and data["weeks"][0]["clear"] >= 1
    status, data = box.call("GET", f"/api/report?week={WEEK}", role="moderator")
    assert status == 200 and data["report"]["week"] == WEEK
    assert box.call("GET", "/api/report?week=../staff", role="moderator")[0] == 400
    assert box.call("GET", "/api/report?week=2026-W01", role="moderator")[0] == 404
    assert box.call("POST", "/api/reports", body={}, role="owner")[0] == 405


def test_routes_with_no_reports_yet(box):    # noqa: F811
    status, data = box.call("GET", "/api/reports", role="moderator")
    assert status == 200 and data["weeks"] == []


# ---------------------------------------------------------------- deploy and the page


@pytest.mark.parametrize("name", ["monkey-report.service", "monkey-report.timer", "monkey-report.sh"])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_units_run_it_weekly_as_monkey_at_the_lowest_priority():
    service = (DEPLOY / "monkey-report.service").read_text()
    assert "User=monkey\n" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-report.sh\n" in service
    assert "Nice=19\n" in service and "IOSchedulingClass=idle\n" in service
    timer = (DEPLOY / "monkey-report.timer").read_text()
    assert "OnCalendar=Mon *-*-* 01:15:00 America/Los_Angeles\n" in timer and "Persistent=true\n" in timer


def test_the_script_is_posix_sh_and_reads_no_secret():
    text = (DEPLOY / "monkey-report.sh").read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert '. "$ENV_FILE"' not in text and "rcon" not in text.lower() and "WEBHOOK" not in text
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR", "STAFF_DIR"}
    assert "--out \"$STAFF_DIR/reports\"" in text


def test_the_reports_tab_is_on_the_page():
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    assert '<script src="reports.js" defer></script>' in html and 'data-tab="reports"' in html
    assert 'id="tab-reports"' in html
    assert '"reports"' in re.search(r"const TABS = \[[^\]]*\]", (PAGE / "panel.js").read_text()).group(0)
    script = (PAGE / "reports.js").read_text(encoding="utf-8")
    assert script.isascii()
    assert "innerHTML" not in script and "eval(" not in script and "document.write" not in script
    assert not re.search(r"\b(confirm|alert)\(", script) and ".style" not in script
    assert "DISCORD_MAX = 1990" in script


def test_write_refuses_a_week_that_is_not_over(live, tmp_path):
    out = tmp_path / "reports"
    with pytest.raises(ValueError, match="isn't over yet"):
        staff_report.write(live, out, WEEK, dt.datetime(2026, 11, 12, 20, tzinfo=dt.UTC))
    assert not out.exists()
    assert staff_report.main(["write", str(live), "--out", str(out), "--week", WEEK,
                              "--at", "2026-11-12T20:00:00Z"]) == 1


def test_without_ledger_the_grace_check_is_skipped_not_clean(live):
    (live / "server" / "world" / "ledger.sqlite").unlink()
    out = report(live)[0]
    skipped = {x["id"]: x["why"] for x in out["skipped"]}
    assert "first joins" in skipped["grace"]
    assert "grace" not in {x["id"] for x in out["clean"]}
    assert cells(out)["Bravo"]["combatlog"]["level"] == "clear"      # the logs' own checks still run


def test_a_cell_counts_its_top_level_and_names_the_others(live):
    # Bravo also breaks and cages a portal of his own: one clear, and the unclear one on Alpha's cage.
    rows = week_rows() + [brk("2026-11-14 09:00:00", "Bravo", "nether_portal", 700, 64, 700),
                          place("2026-11-14 09:00:30", "Bravo", "obsidian", 700, 64, 700)]
    path = live / "server" / "world" / "ledger.sqlite"
    path.unlink()
    ledger(path, rows)
    out = report(live)[0]
    bravo = cells(out)["Bravo"]["portal"]
    assert bravo["level"] == "clear" and bravo["count"] == 1 and bravo["also"] == {"unclear": 1}
    assert [e["level"] for e in bravo["evidence"]] == ["clear", "unclear"]
    assert cells(out)["Alpha"]["pearls"]["also"] == {}


def test_the_job_keeps_the_tools_exit_code():
    text = (DEPLOY / "monkey-report.sh").read_text()
    assert 'log_each python3 -B "$TOOL" write' in text and 'log_each python3 -B "$TOOL" show' in text
    assert "| while" not in text
