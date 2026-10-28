import datetime as dt
import re
import shutil
import subprocess

import pytest
from fake_world import FakeWorld, score_rows
from nbt_writer import nbt
from test_standings import SCOREBOARD
from test_standings import make_world as standings_world

import datapacks
import diplomacy
import drops
import map_border
import outposts
import rcon
import saved_world
import standings
from repo import REPO

UTC = dt.timezone.utc  # noqa: UP017 (the module under test keeps to 3.10)
FILES = outposts.datapack_files()
SPAWN = (-80.0, 416.0)
NOON = dt.datetime(2026, 11, 22, 20, 0, tzinfo=UTC)
LAUNCHED = ("rw.day", "#launched", 1)


def fn(path: str) -> str:
    return FILES[f"{outposts.FN}/{path}.mcfunction"]


def put_storage(world, contents: dict) -> None:
    """The realms namespace's command storage as 26.3 saves it (as tests/test_diplomacy.py writes it)."""
    path = world / "data" / "realms" / "command_storage.dat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(nbt({"DataVersion": 5023, "data": {"contents": contents}}, gzipped=True))


def make_world(root, size=2500.0, target=None, claims=(), scores=(LAUNCHED,), spots=None):
    fake = FakeWorld(root / "world").border(saved_world.OVERWORLD, *SPAWN, size, target)
    (fake.path / "data" / "openpartiesandclaims" / "player-claims").mkdir(parents=True)
    for i, chunks in enumerate(claims):
        fake.claims(f"00000000-0000-0000-0000-00000000000{i}", {saved_world.OVERWORLD: chunks})
    fake.scores(*scores)
    if spots is not None:
        put_storage(fake.path, {"outposts": {"at": {f"o{i}": s for i, s in spots.items()}}})
    return fake.path


BASE = [(cx, cz) for cx in range(10, 14) for cz in range(40, 44)]


def cands(commands: list[str]) -> list[dict]:
    listed = re.search(r"cands set value \[(.*)\]$", commands[0])[1]
    return [{k: int(v) for k, v in re.findall(r"(\w):(-?\d+)", c)} for c in re.findall(r"\{[^}]*\}", listed)]


# ---------------------------------------------------------------- where


def test_nothing_before_the_launch_while_locked_or_while_the_border_grows(tmp_path):
    assert outposts.plan(make_world(tmp_path / "a", scores=()), NOON) == ([], "the season hasn't launched")
    locked = make_world(tmp_path / "b", scores=(LAUNCHED, ("ev.state", "#season_locked", 1)))
    assert outposts.plan(locked, NOON) == ([], "the season is locked")
    growing = make_world(tmp_path / "c", size=2500.0, target=4000.0)
    assert outposts.plan(growing, NOON)[0] == []
    assert outposts.commands(growing, NOON) == []


def test_the_first_run_places_four_outposts_one_in_each_quarter_of_the_ring(tmp_path):
    world = make_world(tmp_path, claims=[BASE])
    out, why = outposts.plan(world, NOON)
    assert why == "" and out[1] == "function realms:outposts/survey {ring:2500,fresh:1}"
    assert all(c.isascii() and len(c.encode()) <= rcon.LIMIT for c in out)
    found = cands(out)
    inner, outer = drops.ring(map_border.Border(*SPAWN, 2500.0))
    claimed = {c for c in BASE}
    assert [c["i"] for c in found[:4]] == [1, 2, 3, 4]       # the first spot for each outpost first
    for c in found:
        assert c["x"] % 16 == 8 and c["z"] % 16 == 8      # a chunk's middle
        dx, dz = c["x"] - SPAWN[0], c["z"] - SPAWN[1]
        assert inner <= max(abs(dx), abs(dz)) <= outer
        assert outposts.quarter(dx, dz) == c["i"]
        assert not outposts.near_claim((c["x"] // 16, c["z"] // 16), claimed, drops.CLAIM_GAP)
    for i in range(1, 5):
        mine = [(c["x"] // 16, c["z"] // 16) for c in found if c["i"] == i]
        assert 1 <= len(mine) <= outposts.CANDIDATES
        assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= outposts.CANDIDATE_GAP
                   for n, a in enumerate(mine) for b in mine[n + 1:])
    # The same hour gives the same spots; the next hour (a retry after water) new ones.
    assert outposts.plan(world, NOON)[0] == out
    assert outposts.plan(world, NOON + dt.timedelta(hours=1))[0] != out


def test_quarters_split_the_ring_by_the_compass():
    assert outposts.quarter(0, -500) == 1 and outposts.quarter(500, 10) == 2
    assert outposts.quarter(-20, 500) == 3 and outposts.quarter(-500, 0) == 4
    assert outposts.quarter(300, -300) == 1 and outposts.quarter(-300, 300) == 3   # diagonals go north and south


def placed():
    return {1: {"x": -72, "z": -584, "y": 70}, 2: {"x": 744, "z": 424, "y": 64},
            3: {"x": -72, "z": 1240, "y": 63}, 4: {"x": -904, "z": 408, "y": 80}}


def test_with_every_outpost_placed_for_this_border_nothing_is_sent(tmp_path):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    assert outposts.plan(world, NOON) == ([], "every outpost has its spot")


def test_a_claim_close_to_one_outpost_moves_only_that_one_and_a_missing_one_is_tried_again(tmp_path):
    spots = placed()
    del spots[4]
    near_east = [(744 // 16 + 2, 424 // 16)]                 # 2 chunks from the East outpost
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=spots, claims=[near_east])
    out, _ = outposts.plan(world, NOON)
    assert out[1] == "function realms:outposts/survey {ring:2500,fresh:0}"
    assert {c["i"] for c in cands(out)} == {2, 4}


def test_a_finished_border_act_places_them_all_again(tmp_path):
    world = make_world(tmp_path, size=4000.0, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    out, _ = outposts.plan(world, NOON)
    assert out[1] == "function realms:outposts/survey {ring:4000,fresh:1}"
    inner, _ = drops.ring(map_border.Border(*SPAWN, 4000.0))
    assert inner == 1250 and all(max(abs(c["x"] - SPAWN[0]), abs(c["z"] - SPAWN[1])) >= inner for c in cands(out))


def test_the_survey_answer_is_logged_in_words():
    survey = "function realms:outposts/survey {ring:2500,fresh:1}"
    assert outposts.meaning(survey, "Function realms:outposts/survey returned 13").endswith(
        "already placed for this border")
    assert outposts.meaning(survey, "Function realms:outposts/survey returned 1").endswith("checking the ground at "
                                                                                           "the spots")
    assert outposts.meaning("data modify storage realms:outposts cands set value []", "") == "spots sent: ok"
    for code in outposts.SURVEY_CODES:
        assert f"return {code}" in fn("survey") or code == 1


# ---------------------------------------------------------------- the live map


def map_conf(world):
    maps = world.parent / map_border.MAPS
    maps.mkdir(parents=True, exist_ok=True)
    for name in ("world.conf", "world_the_nether.conf"):
        shutil.copy(REPO.realms / "defaults" / map_border.MAPS / name, maps / name)
    return maps


def test_send_writes_the_map_marker_set_once_then_only_the_survey(tmp_path):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    maps = map_conf(world)
    nether = (maps / "world_the_nether.conf").read_text(encoding="utf-8")
    assert outposts.commands(world, NOON) == ["bluemap reload"]
    server, log = rcon.Recorder(), []
    assert outposts.send(server, world, NOON, log.append) == 0
    assert server.sent == ["bluemap reload"]
    conf = (maps / "world.conf").read_text(encoding="utf-8")
    assert 'label: "East outpost"' in conf and "position: { x: 744, y: 64, z: 424 }" in conf
    assert (maps / "world_the_nether.conf").read_text(encoding="utf-8") == nether
    assert outposts.commands(world, NOON) == []                 # in step: no reload every hour
    # The marker set comes out whole when there are no outposts (a new season's world).
    assert outposts.with_markers(conf, {}) == (REPO.realms / "defaults" / map_border.MAPS / "world.conf").read_text(
        encoding="utf-8")


def test_a_map_config_without_marker_sets_is_left_alone_with_a_warning(tmp_path):
    world = make_world(tmp_path, spots=placed())
    maps = world.parent / map_border.MAPS
    maps.mkdir(parents=True)
    (maps / "world.conf").write_text('world: "world"\ndimension: "minecraft:overworld"\n', encoding="utf-8")
    warned = []
    assert outposts.map_changes(world, outposts.placed(diplomacy.saved_storage(world)), warned.append) == []
    assert "marker-sets" in warned[0]


def test_a_server_that_isnt_running_is_skipped(tmp_path):
    world = make_world(tmp_path)
    log = []
    assert outposts.send(rcon.Recorder(running=False), world, NOON, log.append) == 0
    assert log == ["server not running: nothing sent"]


# ---------------------------------------------------------------- standings


def test_hours_count_from_the_weeks_baseline_and_points_are_capped():
    scores = {"op.min": {"#f1": 600, "#f2": 59, "#f3": 30}, "op": {"#seq": 7}}
    base = outposts.baseline({"op.min": {"#f1": 400, "#f3": 90}, "op": {"#seq": 3}})
    assert base == {"minutes": {"#f1": 400, "#f3": 90}, "seq": 3}
    assert outposts.hours(scores, base, 1) == 3                 # 200 minutes
    assert outposts.hours(scores, base, 2) == 0                 # 59 minutes: no whole hour
    assert outposts.hours(scores, base, 3) == 0                 # restarted (30 < 90): 30 minutes, all new
    assert outposts.hours(scores, None, 1) == 10 and outposts.hours(scores, base, None) == 0
    assert [outposts.points(h) for h in (0, 1, 19, 20, 45)] == [0, 1, 19, 20, 20]


def test_the_standings_table_adds_outpost_hours_as_a_bonus_like_bounties(tmp_path):
    board = {"DataVersion": SCOREBOARD["DataVersion"], "data": {"PlayerScores": SCOREBOARD["data"]["PlayerScores"]
                                                                + score_rows(("op.min", "#f1", 5 * 60 + 10))}}
    world = standings_world(tmp_path, board)
    put_storage(world, {"factions": {"ids": {"f1": "p-red", "f2": "p-blue"},
                                     "names": {"f1": {"text": "Red Monkeys"}, "f2": {"text": "Blue Herons"}}}})
    data = standings.read_world(world)
    assert data.numbers == {"p-red": 1, "p-blue": 2}
    plain = {r.name: r.points for r in standings.table(standings.World(data.parties, data.claims, {
        k: v for k, v in data.scores.items() if k != "op.min"}, data.labels, data.numbers), None)}
    rows = {r.name: r for r in standings.table(data, {"outposts": {"minutes": {"#f1": 60}}})}
    assert rows["Red Monkeys"].outposts == 4 and rows["Red Monkeys"].points == plain["Red Monkeys"] + 4
    assert rows["Blue Herons"].outposts == 0 and rows["Blue Herons"].points == plain["Blue Herons"]
    text = standings.table_text(list(rows.values()))
    assert text[0].endswith(" Hold") and standings.board_line(rows["Red Monkeys"]).endswith(", outposts 4h]\n")
    assert "outposts" not in standings.board_line(rows["Blue Herons"])
    assert "outpost" in standings.FORMULA and standings.WEIGHTS == (("cup", 40), ("land", 20), ("strength", 20),
                                                                     ("kills", 20))
    assert standings.snapshot(data, NOON)["outposts"] == {"minutes": {"#f1": 310}, "seq": 0}


def test_the_recap_section_names_who_held_longest_and_the_weeks_captures():
    storage = {"factions": {"names": {"f1": {"text": "Red *Monkeys*"}, "f2": {"text": "Blue Herons"}}},
               "outposts": {"log": [{"kind": "capture", "o": 2, "f": 1, "n": 3},
                                    {"kind": "capture", "o": 1, "f": 2, "n": 4},
                                    {"kind": "capture", "o": 2, "f": 2, "n": 5}]}}
    rows = [{"name": "Red *Monkeys*", "outposts": 6}, {"name": "Blue Herons", "outposts": 9}, {"name": "X"}]
    out = outposts.recap_lines(rows, storage, 3)
    assert out[0] == "**Outposts:** held longest by Blue Herons 9 h, Red \\*Monkeys\\* 6 h."
    assert out[1] == "2 captures this week; last, Blue Herons took the East outpost."
    assert outposts.recap_lines([{"name": "X", "outposts": 0}], storage, 5) == []
    assert len(outposts.captures(storage, 9)) == 3              # a log restarted since (a new world): all of it


# ---------------------------------------------------------------- the data pack


def test_the_pack_has_no_problems():
    assert datapacks.problems(datapacks.all_files()) == []   # with every other pack: functions, objectives
    assert all(v.endswith("\n") and "\r" not in v and v.isascii() for v in FILES.values())


def test_only_faction_players_in_survival_outside_the_arena_capture():
    second = fn("o/1/second")
    zone = re.search(r"if entity (@e\[[^\]]*\])", second)[1]
    for part in ("type=minecraft:player", "gamemode=survival", "tag=!ev.arena", "scores={st.faction=1..}",
                 f"dx={outposts.ZONE - 1}"):
        assert part in zone
    assert f"matches {outposts.CAPTURE_SECONDS}.. run function realms:outposts/o/1/captured" in second
    assert "contested" in second


def test_nothing_runs_before_the_launch_and_test_play_is_cleared_once():
    second = fn("second")
    assert second.index("unless score #launched rw.day matches 1 run return 0") < second.index("o/1/second")
    assert "unless score #launched op matches 1 run function realms:outposts/launch" in second
    assert second.index("#season_locked ev.state matches 1 run return 0") < second.index("o/1/second")
    launch = fn("launch")
    for objective in ("op.hold", "op.by", "op.prog", "op.min", "op.id"):
        assert f"scoreboard players reset * {objective}" in launch
    assert "data remove storage realms:outposts at" in launch and "set #launched op 1" in launch


def test_hours_count_only_while_a_rival_is_online_and_a_gone_faction_keeps_nothing():
    credit = fn("o/3/credit")
    assert "unless data storage realms:factions names.f$(h) run return run function realms:outposts/o/3/gone" in credit
    assert "unless score #all op > #mine op run return 0" in credit
    minute = fn("minute")
    assert "unless data storage realms:factions names.f99 run scoreboard players reset #f99 op.min" in minute


def test_nothing_is_given_and_restarts_keep_state():
    every = "\n".join(FILES.values())
    assert not re.search(r"\b(give|effect give|loot give|item replace|xp add)\b", every)
    load = fn("load")
    assert "reset" not in load and "schedule function realms:outposts/check" in load


def test_the_help_lists_real_functions():
    help_ = fn("help")
    for cmd, _ in outposts.HELP:
        assert f"/function realms:outposts/{cmd}" in help_


def test_generated_like_the_other_packs():
    assert "outposts" in datapacks.GENERATORS
    assert set(outposts.packs(REPO)) == {REPO.realms / "datapacks" / outposts.DATAPACK}


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPT = "realms-outposts.sh"
UNITS = ["realms-outposts.service", "realms-outposts.timer"]


@pytest.mark.parametrize("name", [SCRIPT, *UNITS])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_a_timed_job_and_the_timer_runs_hourly():
    text = (DEPLOY / SCRIPT).read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text and "WEBHOOK" not in text
    assert "JOB_TOOL=outposts.py\n" in text and "JOB_WORLD=1\n" in text and "JOB_SHOW=status\n" in text
    assert text.endswith('\ntimed_job "$@"\n')
    for unit in UNITS:
        assert unit in text
    service = (DEPLOY / "realms-outposts.service").read_text()
    assert "User=realms" in service and "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-outposts.sh\n" in service
    assert "OnCalendar=*-*-* *:45:00" in (DEPLOY / "realms-outposts.timer").read_text()
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / SCRIPT)], check=True)


def test_status_runs_on_a_fresh_world(tmp_path, capsys):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed(), claims=[BASE])
    assert outposts.main(["status", str(world), "--at", "2026-11-22T20:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "East: 744 64 424, held by nobody" in out and "every outpost has its spot" in out
