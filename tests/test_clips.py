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
KEY = "123.456"
# A real line's shape from a 26.3 test server (the marker's villager dying), 30 October 2026.
REAL = ("[13:49:15] [Server thread/INFO]: Villager Villager['MONKEY-CLIP v=2|key=123.456|kind=test|title=Two "
        "players|players=;Steve;Alex|factions=;Red Monkeys;Bob's band|dim=overworld|pos=0,201,0'/301, "
        "l='ServerLevel[world]', x=0.50, y=-100.00, z=0.50] died, message: 'MONKEY-CLIP v=2|key=123.456|kind=test|"
        "title=Two players|players=;Steve;Alex|factions=;Red Monkeys;Bob's band|dim=overworld|pos=0,201,0 was killed'")


def test_ships_off_and_checks_the_switch_first():
    load = FILES[f"{FN}/load.mcfunction"]
    assert "scoreboard players add #on cl 0" in load and "set #on" not in load
    mark = FILES[f"{FN}/mark.mcfunction"].splitlines()
    assert mark[2] == "execute unless score #on cl matches 1 run return 0"


def test_the_log_line_carries_every_field_in_order():
    log = FILES[f"{FN}/log.mcfunction"]
    body = log[log.index("MONKEY-CLIP "):log.index('"}')]
    keys = [part.split("=")[0] for part in body.split(" ", 1)[1].split("|")]
    assert keys == ["v", "key", *clips.FIELDS]
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
    (m,) = clips.markers(day, [REAL, "[13:49:16] [Server thread/INFO]: Villager Villager['Bob'/3, l=...] died"], KEY)
    assert m == {"time": "2026-11-07T13:49:15", "version": 2, "kind": "test", "title": "Two players",
                 "dim": "overworld", "players": ["Steve", "Alex"], "factions": ["Red Monkeys", "Bob's band"],
                 "pos": [0, 201, 0]}


def test_a_log_running_past_midnight_moves_to_the_next_day():
    late, early = REAL.replace("[13:49:15]", "[23:59:50]"), REAL.replace("[13:49:15]", "[00:00:10]")
    times = [m["time"] for m in clips.markers(dt.date(2026, 11, 7), [late, early], KEY)]
    assert times == ["2026-11-07T23:59:50", "2026-11-08T00:00:10"]


def test_markers_reads_a_logs_folder(tmp_path, capsys):
    with gzip.open(tmp_path / "2026-11-07-1.log.gz", "wt", encoding="utf-8") as fh:
        fh.write(REAL + "\n")
    latest = tmp_path / "latest.log"
    latest.write_text(REAL.replace("kind=test", "kind=first") + "\n", encoding="utf-8")
    stamp = dt.datetime(2026, 11, 8, 12).timestamp()
    os.utime(latest, (stamp, stamp))
    assert clips.main(["markers", str(tmp_path), "--key", KEY]) == 0
    out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(m["time"][:10], m["kind"]) for m in out] == [("2026-11-07", "test"), ("2026-11-08", "first")]
    assert clips.main(["markers", str(tmp_path), "--key", KEY, "--since", "2026-11-08"]) == 0
    assert [json.loads(x)["kind"] for x in capsys.readouterr().out.splitlines()] == ["first"]


def test_the_pack_draws_the_key_once_and_every_marker_carries_it():
    load = FILES[f"{FN}/load.mcfunction"]
    for k in clips.KEYS:
        assert f"execute unless score {k} cl matches 1.. store result score {k} cl run random value" in load
    assert "|key=$(k1).$(k2)|" in FILES[f"{FN}/log.mcfunction"]


@pytest.mark.parametrize("forged, flagged", [
    # chat: a player's line after the thread never matches
    ("[13:49:15] [Server thread/INFO]: <Bob> Villager Villager['MONKEY-CLIP v=2|key=123.456|kind=x|title=x'/1, "
     "l='ServerLevel[world]', x=0.50, y=-100.00, z=0.50] died, message: 'x'", False),
    (REAL.replace("[Server thread/INFO]", "[Async Chat Thread - #0/INFO]"), False),
    # a named villager dying anywhere but under the floor
    (REAL.replace("y=-100.00", "y=64.00"), True),
    # without the world's key, or with another one
    (REAL.replace("key=123.456|", ""), True),
    (REAL.replace("key=123.456", "key=1.2"), True),
])
def test_forged_lines_are_left_out(forged, flagged):
    left_out = []
    assert clips.markers(dt.date(2026, 11, 7), [forged], KEY, left_out) == []
    assert len(left_out) == int(flagged)


def test_the_key_comes_from_the_world(tmp_path, capsys, monkeypatch):
    import saved_world

    monkeypatch.setattr(saved_world, "scoreboard", lambda world: saved_world.Scoreboard(
        {"cl": {"#key1": 123, "#key2": 456}}, {}, []))
    assert clips.world_key(tmp_path) == KEY
    assert clips.main(["key", str(tmp_path)]) == 0 and capsys.readouterr().out.strip() == KEY
    (tmp_path / "latest.log").write_text(REAL + "\n", encoding="utf-8")
    assert clips.main(["markers", str(tmp_path), "--world", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "test"
    with pytest.raises(SystemExit):
        clips.main(["markers", str(tmp_path)])  # a key, or the world to read it from, is required


@pytest.mark.parametrize("swap", [
    ("factions=;Red Monkeys;Bob's band", "factions=;Red Monkeys|kind=boss;Bob's band"),   # a faction with | and =
    ("factions=;Red Monkeys;Bob's band", "factions=;Red=Monkeys;Bob's band"),
    ("title=Two players", "title=Two players|title=Other"),                               # a key twice
    ("|dim=overworld", "|extra=1|dim=overworld"),                                         # an unexpected key
    ("players=;Steve;Alex", "players=;Steve Alex"),                                       # not a player name
    ("pos=0,201,0", "pos=0,201"),
])
def test_a_body_with_injected_or_odd_fields_is_forged(swap):
    left_out = []
    assert clips.markers(dt.date(2026, 11, 7), [REAL.replace(*swap, 1)], KEY, left_out) == []
    assert len(left_out) == 1


def test_no_faction_name_the_board_keeps_can_break_a_marker():
    import standings

    for name in ("Red|kind=boss", "a;b=c", 'say "hi"'):
        clean = standings.board_name(name)
        assert not set(clean) & set('|;="') and clips.parse(REAL.split("MONKEY-CLIP ")[1].split("'/")[0].replace(
            "Red Monkeys", clean))
