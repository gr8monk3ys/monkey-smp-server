import datetime as dt
import re
import shutil
import subprocess

import pytest
from fake_world import FakeWorld, score_rows
from nbt_writer import nbt
from test_deploy_lib import job, needs_dash, sh  # noqa: F401 (sh is test_deploy_lib's fixture)
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
    """The monkey namespace's command storage as 26.3 saves it (as tests/test_diplomacy.py writes it)."""
    path = world / "data" / "monkey" / "command_storage.dat"
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
    listed = re.search(r",cands:\[(.*)\]\}$", commands[-1])[1]
    return [{k: int(v) for k, v in re.findall(r"(\w):(-?\d+)", c)} for c in re.findall(r"\{[^}]*\}", listed)]


def survey_of(commands: list[str]) -> str:
    """The survey command without its spots."""
    return re.sub(r",cands:\[.*\]\}$", "}", commands[-1])


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
    assert why == "" and len(out) == 1 and survey_of(out) == "function monkey:outposts/survey {ring:2500,fresh:1}"
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
        assert not drops.near_claim((c["x"] // 16, c["z"] // 16), claimed, drops.CLAIM_GAP)
    for i in range(1, 5):
        mine = [(c["x"] // 16, c["z"] // 16) for c in found if c["i"] == i]
        assert 1 <= len(mine) <= outposts.CANDIDATES
        assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= outposts.CANDIDATE_GAP
                   for n, a in enumerate(mine) for b in mine[n + 1:])
    # The same hour gives the same spots; the next hour (a retry after water) new ones.
    assert outposts.plan(world, NOON)[0] == out
    assert outposts.plan(world, NOON + dt.timedelta(hours=1))[0] != out


def test_the_spots_come_from_drops_sampler_and_claim_check(monkeypatch):
    drawn = []

    def ring_chunks(border, rng):
        drawn.append(border)
        yield (0, -40), 8, -632
    monkeypatch.setattr(drops, "ring_chunks", ring_chunks)
    monkeypatch.setattr(drops, "near_claim", lambda chunk, claims, gap=drops.CLAIM_GAP: False)
    border = map_border.Border(*SPAWN, 2500.0)
    assert outposts.candidates(border, set(), "s", [1, 2]) == [{"i": 1, "x": 8, "z": -632}]
    assert drawn == [border] and not hasattr(outposts, "near_claim") and not hasattr(outposts, "DRAWS")


def test_a_survey_too_long_for_one_command_sends_fewer_spots(tmp_path, monkeypatch):
    monkeypatch.setattr(outposts.server, "LIMIT", 300)
    out, why = outposts.plan(make_world(tmp_path, claims=[BASE]), NOON)
    assert why == "" and len(out) == 1 and len(out[0].encode()) <= 300 and 1 <= len(cands(out)) < 16


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
    assert survey_of(out) == "function monkey:outposts/survey {ring:2500,fresh:0}"
    assert {c["i"] for c in cands(out)} == {2, 4}


def test_a_finished_border_act_places_them_all_again(tmp_path):
    world = make_world(tmp_path, size=4000.0, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    out, _ = outposts.plan(world, NOON)
    assert survey_of(out) == "function monkey:outposts/survey {ring:4000,fresh:1}"
    inner, _ = drops.ring(map_border.Border(*SPAWN, 4000.0))
    assert inner == 1250 and all(max(abs(c["x"] - SPAWN[0]), abs(c["z"] - SPAWN[1])) >= inner for c in cands(out))


def test_the_survey_answer_is_logged_in_words():
    survey = "function monkey:outposts/survey {ring:2500,fresh:1,cands:[{i:1,x:8,z:-632}]}"
    assert outposts.meaning(survey, "Function monkey:outposts/survey returned 13") == (
        "function monkey:outposts/survey: already placed for this border")
    assert outposts.meaning(survey, "Function monkey:outposts/survey returned 1").endswith("checking the ground at "
                                                                                           "the spots")
    reset = "scoreboard players reset #f3 op.min"
    assert outposts.meaning(reset, "") == f"{reset}: ok"
    for code in outposts.SURVEY_CODES:
        assert f"return {code}" in fn("survey") or code == 1


def test_a_running_survey_keeps_its_spots_and_the_spots_come_with_the_survey():
    survey = fn("survey").splitlines()
    put = survey.index("$data modify storage monkey:outposts cands set value $(cands)")
    for check in ("return 10", "return 11", "return 12", "return 13", "return 14", "return 15"):
        assert next(n for n, line in enumerate(survey) if line.endswith(check)) < put
    assert put < next(n for n, line in enumerate(survey) if line.endswith("set #busy op 1"))
    every = "\n".join(FILES.values())
    assert every.count("cands set value") == 1       # nothing else (and no RCON command) writes the spots


# ---------------------------------------------------------------- the live map


def map_conf(world):
    maps = world.parent / map_border.MAPS
    maps.mkdir(parents=True, exist_ok=True)
    for name in ("world.conf", "world_the_nether.conf"):
        shutil.copy(REPO.monkey / "defaults" / map_border.MAPS / name, maps / name)
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
    assert outposts.with_markers(conf, {}) == (REPO.monkey / "defaults" / map_border.MAPS / "world.conf").read_text(
        encoding="utf-8")


def test_a_failed_map_write_sends_no_reload(tmp_path, monkeypatch):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    maps = map_conf(world)
    before = (maps / "world.conf").read_text(encoding="utf-8")

    def refuse(self, *args, **kwargs):
        raise PermissionError("read-only file system")
    monkeypatch.setattr(outposts.Path, "write_text", refuse)
    server, log = rcon.Recorder(), []
    assert outposts.send(server, world, NOON, log.append) == 0
    assert server.sent == [] and (maps / "world.conf").read_text(encoding="utf-8") == before
    assert len(log) == 1 and log[0].startswith("map: could not write ") and log[0].endswith("; no reload")


def test_a_map_config_that_cant_be_written_is_warned_about_and_never_reloads(tmp_path):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed())
    conf = map_conf(world) / "world.conf"
    conf.chmod(0o444)
    try:
        warned = []
        assert outposts.map_changes(world, placed(), warned.append) == [] and "can't be written" in warned[0]
        assert outposts.commands(world, NOON) == []
        server, log = rcon.Recorder(), []
        assert outposts.send(server, world, NOON, log.append) == 0 and server.sent == []
        assert log == [f"map: {conf} can't be written: the map's outposts are out of date"]
    finally:
        conf.chmod(0o644)


def test_the_saved_world_is_read_once_a_run(tmp_path, monkeypatch):
    world = make_world(tmp_path, claims=[BASE], spots=placed())
    map_conf(world)
    reads = []
    real = diplomacy.saved_storage
    monkeypatch.setattr(outposts.diplomacy, "saved_storage", lambda w: reads.append(w) or real(w))
    server = rcon.Recorder()
    outposts.send(server, world, NOON, [].append)
    assert len(reads) == 1 and server.sent[-1] == "bluemap reload" and len(server.sent) == 2
    reads.clear()
    outposts.commands(world, NOON)
    assert len(reads) == 1


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
    scores = {"op.min": {"#f1": 600, "#f2": 59, "#f3": 210}, "op": {"#seq": 7, "#epoch": 77}}
    base = outposts.baseline({"op.min": {"#f1": 400, "#f3": 90}, "op": {"#seq": 3, "#epoch": 77}})
    assert base == {"epoch": 77, "minutes": {"#f1": 400, "#f3": 90}, "seq": 3}
    assert outposts.hours(scores, base, 1) == 3                 # 200 minutes
    assert outposts.hours(scores, base, 2) == 0                 # 59 minutes: no whole hour
    assert outposts.hours(scores, base, 3) == 2                 # 120 minutes
    assert outposts.hours(scores, None, 1) == 10 and outposts.hours(scores, base, None) == 0
    assert [outposts.points(h) for h in (0, 1, 19, 20, 45)] == [0, 1, 19, 20, 20]


def test_a_staff_penalty_lowers_the_weeks_hours_and_never_adds_any():
    base = outposts.baseline({"op.min": {"#f3": 300}, "op": {"#epoch": 77}})
    held = {"op.min": {"#f3": 300 + 150}, "op": {"#epoch": 77}}
    assert outposts.hours(held, base, 3) == 2
    held["op.min"]["#f3"] -= 120                                   # scoreboard players remove #f3 op.min 120
    assert outposts.hours(held, base, 3) == 0
    held["op.min"]["#f3"] -= 120                                   # below the week's start: still none, not 3
    assert outposts.hours(held, base, 3) == 0


def test_a_new_launch_counts_every_minute_since_it():
    test_play = outposts.baseline({"op.min": {"#f1": 900}, "op": {"#epoch": 12}})
    assert outposts.hours({"op.min": {"#f1": 130}, "op": {"#epoch": 99}}, test_play, 1) == 2
    before = outposts.baseline({"op.min": {}, "op": {}})            # snapshot taken before the launch
    assert before["epoch"] == 0 and outposts.hours({"op.min": {"#f1": 130}, "op": {"#epoch": 99}}, before, 1) == 2
    assert outposts.hours({"op.min": {"#f1": 130}}, {"minutes": {"#f1": 60}}, 1) == 2   # no epoch on either side
    launch = fn("launch")
    assert "execute store result score #epoch op run random value 1..1000000000" in launch
    assert "execute store result storage monkey:outposts epoch int 1 run scoreboard players get #epoch op" in launch


def test_the_standings_table_adds_outpost_hours_as_a_bonus_like_bounties(tmp_path):
    board = {"DataVersion": SCOREBOARD["DataVersion"], "data": {"PlayerScores": SCOREBOARD["data"]["PlayerScores"]
                                                                + score_rows(("op.min", "#f1", 5 * 60 + 10),
                                                                             ("op", "#epoch", 77))}}
    world = standings_world(tmp_path, board)
    put_storage(world, {"factions": {"ids": {"f1": "p-red", "f2": "p-blue"},
                                     "names": {"f1": {"text": "Red Monkeys"}, "f2": {"text": "Blue Herons"}}}})
    data = standings.read_world(world)
    assert data.numbers == {"p-red": 1, "p-blue": 2}
    plain = {r.name: r.points for r in standings.table(standings.World(data.parties, data.claims, {
        k: v for k, v in data.scores.items() if k != "op.min"}, data.labels, data.numbers), None)}
    rows = {r.name: r for r in standings.table(data, {"outposts": {"epoch": 77, "minutes": {"#f1": 60}}})}
    assert rows["Red Monkeys"].outposts == 4 and rows["Red Monkeys"].points == plain["Red Monkeys"] + 4
    assert rows["Blue Herons"].outposts == 0 and rows["Blue Herons"].points == plain["Blue Herons"]
    text = standings.table_text(list(rows.values()))
    assert text[0].endswith(" Hold") and standings.board_line(rows["Red Monkeys"]).endswith(", outposts 4h]\n")
    assert "outposts" not in standings.board_line(rows["Blue Herons"])
    assert "outpost" in standings.FORMULA and standings.WEIGHTS == (("cup", 40), ("land", 20), ("strength", 20),
                                                                     ("kills", 20))
    assert standings.snapshot(data, NOON)["outposts"] == {"epoch": 77, "minutes": {"#f1": 310}, "seq": 0}


def test_a_damaged_storage_file_leaves_outpost_hours_out_of_the_table(tmp_path, capsys):
    world = standings_world(tmp_path, SCOREBOARD)
    (world / diplomacy.STORAGE_FILE).parent.mkdir(parents=True, exist_ok=True)
    (world / diplomacy.STORAGE_FILE).write_bytes(b"\x1f\x8bnot really gzip")
    data = standings.read_world(world)
    assert data.numbers == {} and standings.table(data, None)
    assert "outpost hours are left out this run" in capsys.readouterr().err


def test_the_recap_section_names_who_held_longest_and_the_weeks_captures():
    storage = {"factions": {"names": {"f1": {"text": "Red *Monkeys*"}, "f2": {"text": "Blue Herons"}}},
               "outposts": {"epoch": 77, "log": [{"kind": "capture", "o": 2, "f": 1, "n": 3},
                                                 {"kind": "capture", "o": 1, "f": 2, "n": 4},
                                                 {"kind": "capture", "o": 2, "f": 2, "n": 5}]}}
    rows = [{"name": "Red *Monkeys*", "outposts": 6}, {"name": "Blue Herons", "outposts": 9}, {"name": "X"}]
    out = outposts.recap_lines(rows, storage, {"epoch": 77, "seq": 3})
    assert out[0] == "**Outposts:** held longest by Blue Herons 9 h, Red \\*Monkeys\\* 6 h."
    assert out[1] == "2 captures this week; last, Blue Herons took the East outpost."
    assert outposts.recap_lines([{"name": "X", "outposts": 0}], storage, {"epoch": 77, "seq": 5}) == []
    assert len(outposts.captures(storage, {"epoch": 12, "seq": 9})) == 3     # another launch (a new world): all of it
    assert len(outposts.captures(storage, None)) == 3


def test_the_capture_log_keeps_its_newest_entries():
    log = fn("log")
    assert f"if data storage monkey:outposts log[{outposts.LOG_KEEP}] run data remove storage monkey:outposts log[0]" \
        in log
    assert log.index("log[-1].n") < log.index(f"log[{outposts.LOG_KEEP}]")


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
    assert f"matches {outposts.CAPTURE_SECONDS}.. run function monkey:outposts/o/1/captured" in second
    assert "contested" in second


def test_nothing_runs_before_the_launch_and_test_play_is_cleared_once():
    second = fn("second")
    assert second.index("unless score #launched rw.day matches 1 run return 0") < second.index("o/1/second")
    assert "unless score #launched op matches 1 run function monkey:outposts/launch" in second
    assert second.index("#season_locked ev.state matches 1 run return 0") < second.index("o/1/second")
    launch = fn("launch")
    for objective in ("op.hold", "op.by", "op.prog", "op.min", "op.id"):
        assert f"scoreboard players reset * {objective}" in launch
    assert "data remove storage monkey:outposts at" in launch and "set #launched op 1" in launch


def test_hours_count_only_while_a_rival_is_online_and_a_gone_faction_keeps_nothing():
    credit = fn("o/3/credit")
    assert "unless data storage monkey:factions names.f$(h) run return run function monkey:outposts/o/3/gone" in credit
    assert "unless score #all op > #mine op run return 0" in credit
    minute = fn("minute")
    assert "names.f" not in minute and len(minute.splitlines()) < 12     # no poll of all 99 numbers a minute


def test_a_gone_factions_minutes_are_reset_by_the_hourly_run(tmp_path):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500), ("op.min", "#f1", 90),
                                         ("op.min", "#f2", 30), ("op.min", "#f12", 5)), spots=placed())
    put_storage(world, {"factions": {"names": {"f1": {"text": "Red Monkeys"}}},
                        "outposts": {"at": {f"o{i}": s for i, s in placed().items()}}})
    assert outposts.plan(world, NOON) == (["scoreboard players reset #f12 op.min",
                                           "scoreboard players reset #f2 op.min"], "every outpost has its spot")
    locked = make_world(tmp_path / "l", scores=(LAUNCHED, ("ev.state", "#season_locked", 1), ("op.min", "#f2", 30)))
    assert outposts.plan(locked, NOON)[0] == ["scoreboard players reset #f2 op.min"]   # the lock keeps no one's
    early = make_world(tmp_path / "e", scores=(("op.min", "#f2", 30),))
    assert outposts.plan(early, NOON) == ([], "the season hasn't launched")


def test_a_survey_stops_cleanly_when_outposts_go_off_or_the_season_locks():
    stopped = fn("stopped")
    assert "unless score #auto op matches 1 run return 1" in stopped
    assert "if score #season_locked ev.state matches 1 run return 1" in stopped and stopped.endswith("return 0\n")
    pick, check = fn("pick").splitlines(), fn("check").splitlines()
    assert pick[1] == "execute if function monkey:outposts/stopped run return run function monkey:outposts/done"
    assert check.index("execute if function monkey:outposts/stopped run return run function monkey:outposts/abort") \
        < next(n for n, line in enumerate(check) if "check_at" in line)
    abort = fn("abort")
    assert "function monkey:outposts/unload with storage monkey:outposts cand" in abort
    assert "function monkey:outposts/done" in abort and "tellraw" not in abort


def test_centres_are_right_for_negative_coordinates_too():
    every = "\n".join(FILES.values())
    assert ").5" not in every
    near = fn("o/1/near")
    assert "positioned $(x) $(ly) $(z) align xz run summon minecraft:text_display ~0.5 ~ ~0.5 " in near
    assert "positioned $(x) $(ly) $(z) align xz run particle minecraft:end_rod ~0.5 ~ ~0.5 " in near
    assert "positioned $(x) 0 $(z) align xz positioned over motion_blocking_no_leaves" in fn("check_at")


def test_a_moved_outposts_old_label_goes_before_one_label_is_kept():
    near = fn("o/2/near").splitlines()
    stale = near.index("execute as @e[type=minecraft:text_display,tag=op.l2] unless score @s op.id = #o2 op.id run "
                       "kill @s")
    summon = next(n for n, line in enumerate(near) if "summon minecraft:text_display" in line)
    dedupe = near.index("execute if score #lc op matches 2.. run function monkey:outposts/o/2/one_label")
    assert stale < summon < dedupe
    one = fn("o/2/one_label")
    assert "tag @e[type=minecraft:text_display,tag=op.l2,limit=1] add op.keep" in one
    assert "kill @e[type=minecraft:text_display,tag=op.l2,tag=!op.keep]" in one


def test_only_a_new_label_gets_its_text_each_second_and_held_ones_refresh_each_minute():
    near = fn("o/1/near")
    assert "execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity" not in near
    assert "execute as @e[type=minecraft:text_display,tag=op.new] run data modify entity @s text" in near
    minute = fn("o/1/minute")
    assert "function monkey:outposts/o/1/label" in minute
    assert "execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text" in minute


def test_nothing_is_given_and_restarts_keep_state():
    every = "\n".join(FILES.values())
    assert not re.search(r"\b(give|effect give|loot give|item replace|xp add)\b", every)
    load = fn("load")
    assert "reset" not in load and "schedule function monkey:outposts/check" in load


def test_the_help_lists_real_functions():
    help_ = fn("help")
    for cmd, _ in outposts.HELP:
        assert f"/function monkey:outposts/{cmd}" in help_


def test_generated_like_the_other_packs():
    assert "outposts" in datapacks.GENERATORS
    assert set(outposts.packs(REPO)) == {REPO.monkey / "datapacks" / outposts.DATAPACK}


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPT = "monkey-outposts.sh"
UNITS = ["monkey-outposts.service", "monkey-outposts.timer"]


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
    service = (DEPLOY / "monkey-outposts.service").read_text()
    assert "User=monkey" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-outposts.sh\n" in service
    assert "OnCalendar=*-*-* *:45:00" in (DEPLOY / "monkey-outposts.timer").read_text()
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / SCRIPT)], check=True)


def test_status_runs_on_a_fresh_world(tmp_path, capsys):
    world = make_world(tmp_path, scores=(LAUNCHED, ("op", "#ring", 2500)), spots=placed(), claims=[BASE])
    assert outposts.main(["status", str(world), "--at", "2026-11-22T20:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "East: 744 64 424, held by nobody" in out and "every outpost has its spot" in out


@pytest.fixture
def outposts_job(request, tmp_path):
    """test_deploy_lib's job() for deploy/monkey-outposts.sh: (exit code, its logged lines, calls)."""
    run = request.getfixturevalue("sh")
    (tmp_path / "repo" / "tools").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / "tools" / "outposts.py").write_text("")
    return lambda *args, **env: job(run, tmp_path, SCRIPT, *args, **env)


@needs_dash
def test_the_timer_with_nothing_to_place_takes_no_lock(outposts_job):
    code, logged, calls = outposts_job()
    assert code == 0 and logged == [] and len(calls) == 1
    assert calls[0].startswith("python3 -B ") and calls[0].endswith("outposts.py commands /srv/live/server/world")


@needs_dash
def test_the_timer_sends_under_the_deploy_lock(outposts_job):
    code, logged, calls = outposts_job(FAKE_OUT_python3=r"bluemap reload: ok\n")
    assert code == 0 and logged == ["bluemap reload: ok"]
    send = calls.index("flock -w 1800 9") + 1
    assert calls[send].startswith("python3 -B -u ") and calls[send].endswith(
        "outposts.py send /srv/live/server/world --docker /srv/live/docker")
    code, logged, _ = outposts_job(FAKE_OUT_python3="x", FAKE_RC_send="1")
    assert code == 1 and logged[-1] == "ERROR: not every command went through (the timer tries again in an hour)"


@needs_dash
def test_check_shows_the_outposts_and_the_commands_and_install_needs_root(outposts_job):
    code, logged, calls = outposts_job("--check", FAKE_OUT_python3=r"bluemap reload\n")
    assert code == 0 and logged[:3] == ["bluemap reload", "commands for now:", "  bluemap reload"]
    assert not any(c.startswith("flock") for c in calls) and " status /srv/live/server/world" in calls[0]
    _, logged, _ = outposts_job("--check")
    assert "  none (before the launch, or nothing to place or move)" in logged
    code, logged, _ = outposts_job("--install")
    assert code == 1 and logged == ["ERROR: run as root: it installs systemd units"]
