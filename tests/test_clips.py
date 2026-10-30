import datetime as dt
import gzip
import json
import os

import pytest

import clips
import drops
import firsts
import omens
import outposts

FILES = clips.datapack_files()
FN = "data/monkey/function/clips"
# A real line from a 26.3 test server (the marker's villager dying), 30 October 2026.
REAL = ("[13:49:15] [Server thread/INFO]: Villager Villager['MONKEY-CLIP v=1|kind=test|title=Two players|"
        "players=;Steve;Alex|factions=;Red Monkeys;Bob's band|dim=overworld|pos=0,201,0'/301, l='ServerLevel[world]',"
        " x=0.50, y=-99.00, z=0.50] died, message: 'MONKEY-CLIP v=1|kind=test|title=Two players|players=;Steve;Alex|"
        "factions=;Red Monkeys;Bob's band|dim=overworld|pos=0,201,0 was killed'")


def test_ships_off_and_checks_the_switch_first():
    load = FILES[f"{FN}/load.mcfunction"]
    assert "scoreboard players add #on cl 0" in load and "set #on" not in load
    mark = FILES[f"{FN}/mark.mcfunction"].splitlines()
    assert mark[2] == "execute unless score #on cl matches 1 run return 0"


def test_the_log_line_carries_every_field_in_order():
    log = FILES[f"{FN}/log.mcfunction"]
    body = log[log.index("MONKEY-CLIP "):log.index('"}')]
    keys = [part.split("=")[0] for part in body.split(" ", 1)[1].split("|")]
    assert keys == ["v", *clips.FIELDS]
    assert "minecraft:villager ~ -100 ~" in log and "Silent:1b" in log
    assert f"kill @e[type=minecraft:villager,tag={clips.LOG_TAG}]" in log


def test_mark_refuses_text_that_would_break_the_line():
    assert clips.mark("boss", "The boss is down") == (
        'function monkey:clips/mark {kind:"boss",title:"The boss is down",other:""}')
    for kind, title in (("boss", 'a "quote"'), ("boss", "a|b"), ("boss", "a;b"), ("Boss", "ok")):
        with pytest.raises(ValueError):
            clips.mark(kind, title)


def test_the_big_moments_call_it():
    claims = firsts.datapack_files()
    for m in firsts.MILESTONES:
        claim = claims[f"data/monkey/function/firsts/claim/{m['id']}.mcfunction"]
        assert clips.mark("first", f"Server First: {m['name']}") in claim
    land = drops.datapack_files()["data/monkey/function/drops/land.mcfunction"]
    assert 'kind:"drop"' in land and 'kind:"meteor"' in land
    assert "function monkey:clips/mark with storage monkey:omens clip" in omens.datapack_files()[
        "data/monkey/function/omens/hunted/kill.mcfunction"]
    taken = [v for k, v in outposts.datapack_files().items() if k.endswith("/captured.mcfunction")]
    assert len(taken) == 4 and all('kind:"outpost"' in t for t in taken)


def test_parse_reads_a_real_line():
    day = dt.date(2026, 11, 7)
    (m,) = clips.markers(day, [REAL, "[13:49:16] [Server thread/INFO]: Villager Villager['Bob'/3, l=...] died"])
    assert m == {"time": "2026-11-07T13:49:15", "version": 1, "kind": "test", "title": "Two players",
                 "dim": "overworld", "players": ["Steve", "Alex"], "factions": ["Red Monkeys", "Bob's band"],
                 "pos": [0, 201, 0]}


def test_a_log_running_past_midnight_moves_to_the_next_day():
    late, early = REAL.replace("[13:49:15]", "[23:59:50]"), REAL.replace("[13:49:15]", "[00:00:10]")
    times = [m["time"] for m in clips.markers(dt.date(2026, 11, 7), [late, early])]
    assert times == ["2026-11-07T23:59:50", "2026-11-08T00:00:10"]


def test_markers_reads_a_logs_folder(tmp_path, capsys):
    with gzip.open(tmp_path / "2026-11-07-1.log.gz", "wt", encoding="utf-8") as fh:
        fh.write(REAL + "\n")
    latest = tmp_path / "latest.log"
    latest.write_text(REAL.replace("kind=test", "kind=first") + "\n", encoding="utf-8")
    stamp = dt.datetime(2026, 11, 8, 12).timestamp()
    os.utime(latest, (stamp, stamp))
    assert clips.main(["markers", str(tmp_path)]) == 0
    out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(m["time"][:10], m["kind"]) for m in out] == [("2026-11-07", "test"), ("2026-11-08", "first")]
    assert clips.main(["markers", str(tmp_path), "--since", "2026-11-08"]) == 0
    assert [json.loads(x)["kind"] for x in capsys.readouterr().out.splitlines()] == ["first"]
