import gzip
import json
import struct
import zipfile

import pytest

import datapacks
import season
import wardrobe


def nbt(value, name="") -> bytes:
    """A tiny NBT writer for test fixtures: dicts, lists, strings and ints (ints are TAG_Int)."""
    def tag(v) -> int:
        return 10 if isinstance(v, dict) else 9 if isinstance(v, list) else 8 if isinstance(v, str) else 3

    def payload(v) -> bytes:
        if isinstance(v, dict):
            return b"".join(bytes([tag(x)]) + string(k) + payload(x) for k, x in v.items()) + b"\x00"
        if isinstance(v, list):
            return bytes([tag(v[0]) if v else 0]) + struct.pack(">i", len(v)) + b"".join(payload(x) for x in v)
        if isinstance(v, str):
            return string(v)
        return struct.pack(">i", v)

    def string(s: str) -> bytes:
        raw = s.encode()
        return struct.pack(">H", len(raw)) + raw
    return bytes([10]) + string(name) + payload(value)


def scores(*rows):
    # 26.3 leaves Score out when it is 0
    return [{"Objective": o, "Name": n, "Locked": 1} | ({"Score": s} if s else {}) for o, n, s in rows]


SCOREBOARD = {"DataVersion": 5023, "data": {
    "Objectives": [{"Name": "rw.days", "DisplayName": "rw.days"}],
    "PlayerScores": scores(
        ("rw.days", "AlexFake", 41), ("rw.months", "AlexFake", 3), ("rw.founder", "AlexFake", 1),
        ("rw.events", "AlexFake", 4), ("rw.hallowtide", "AlexFake", 1), ("rw.months.seen", "AlexFake", 3),
        ("rw.play", "AlexFake", 360000), ("rw.hours", "AlexFake", 5), ("rw.lastday", "AlexFake", 77),
        ("rw.play", "SamFake", 72000), ("rw.playbase", "SamFake", 144000), ("rw.days", "SamFake", 2),
        ("rw.day", "#today", 77), ("rw.day", "#season", 1), ("rw.const", "#hour", 72000), ("rw.tier", "SamFake", 0),
        ("ev.cup", "red", 120), ("Strength_SMP+Strength_Level", "AlexFake", 3)),
    "Teams": [
        {"Name": "tier_banner", "DisplayName": "tier_banner", "TeamColor": "green", "Players": ["AlexFake"]},
        {"Name": "champion", "DisplayName": "champion", "TeamColor": "gold",
         "MemberNamePrefix": {"text": "[S1 Champion] ", "color": "gold"}, "Players": ["SamFake"]},
        {"Name": "in.castle", "DisplayName": "in.castle", "TeamColor": "dark_red", "Players": ["AlexFake"]}],
}}


def test_reads_what_it_writes():
    assert season.read_nbt(nbt(SCOREBOARD)) == SCOREBOARD


def test_carry_puts_back_the_wardrobe_and_teams(tmp_path):
    old, new = tmp_path / "old" / "world", tmp_path / "new" / "world"
    (old / "data" / "minecraft").mkdir(parents=True)
    (old / "data" / "minecraft" / "scoreboard.dat").write_bytes(gzip.compress(nbt(SCOREBOARD)))
    assert season.main(["carry", str(old), "--into", str(new), "--season", "2"]) == 0
    pack = new / "datapacks" / "realms-carry"
    assert json.loads((pack / "pack.mcmeta").read_text())["pack"]["min_format"] == datapacks.DATA_FORMAT
    assert json.loads((pack / "data/minecraft/tags/function/load.json").read_text()) == {"values": ["realms:carry/run"]}
    run = (pack / "data/realms/function/carry/run.mcfunction").read_text().splitlines()
    guard = run.index("execute if score #carried rw.day matches 1 run return 0")
    assert run.index("scoreboard players set #season rw.day 2") > guard
    for line in ["scoreboard players set #today rw.day 77", "scoreboard players set AlexFake rw.days 41",
                 "scoreboard players set AlexFake rw.months 3", "scoreboard players set AlexFake rw.founder 1",
                 "scoreboard players set AlexFake rw.events 4", "scoreboard players set AlexFake rw.hallowtide 1",
                 "scoreboard players set AlexFake rw.months.seen 3", "scoreboard players set AlexFake rw.lastday 77",
                 "scoreboard objectives add rw.hallowtide dummy",
                 # play time becomes the base the new world's hours start from
                 "scoreboard players set AlexFake rw.playbase 360000",
                 "scoreboard players set SamFake rw.playbase 216000",
                 "team add tier_banner", "team modify tier_banner color green", "team join tier_banner AlexFake",
                 'team modify champion prefix {"text": "[S1 Champion] ", "color": "gold"}',
                 "team join champion SamFake",
                 "scoreboard players set SamFake rw.tier 0", "scoreboard players set #carried rw.day 1"]:
        assert line in run, line
    text = "\n".join(run)
    for absent in ("rw.hours", "rw.const", "rw.play ", "ev.cup", "Strength", "in.castle", "#season rw.day 1"):
        assert absent not in text, absent
    assert run[-1] == "say Carried 2 players' wardrobe scores and 2 teams into season 2."


def test_every_wardrobe_score_is_carried():
    """A wardrobe score left out of the carry would quietly reset every player's progress next season."""
    load = wardrobe.datapack_files()["data/realms/function/wardrobe/load.mcfunction"]
    created = {line.split()[3] for line in load.splitlines() if line.startswith("scoreboard objectives add rw.")}
    assert created - season.NOT_CARRIED >= {"rw.days", "rw.months", "rw.events", "rw.midwinter", "rw.events.seen"}
    assert season.NOT_CARRIED - created <= set()   # nothing named here that the wardrobe doesn't make
    unlocks = {s["unlock"][0] for _, _, s in wardrobe.skins()}
    assert not unlocks & season.NOT_CARRIED - {"rw.hours"}   # hours come back through rw.playbase


def test_download_keeps_the_world_and_leaves_out_private_files(tmp_path):
    world = tmp_path / "backup" / "world"
    keep = ["level.dat", "dimensions/minecraft/overworld/region/r.0.0.mca", "players/data/a.dat",
            "players/stats/a.json", "data/minecraft/scoreboard.dat", "data/openpartiesandclaims/server-info.nbt",
            "datapacks/realms-wardrobe/pack.mcmeta"]
    drop = ["ledger.sqlite", "session.lock", "level.dat_old", "serverconfig/x.toml", "scripts/a.js",
            "dimensions/minecraft/overworld/data/DistantHorizons.sqlite", "data/baguettelib/player_activity.dat",
            "data/mezz_config/server-id.txt", "datapacks/realms-carry/pack.mcmeta"]
    for rel in keep + drop:
        (world / rel).parent.mkdir(parents=True, exist_ok=True)
        (world / rel).write_bytes(b"x")
    (tmp_path / "backup" / "server.properties").write_text("rcon.password=secret\n")
    out = tmp_path / "s.zip"
    assert season.main(["download", str(world), "--season", "I", "--modpack", "2.5.0", "--out", str(out)]) == 0
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {f"Monkey SMP Season I/{rel}" for rel in keep} | {"Monkey SMP Season I/READ ME.txt"}
    readme = zipfile.ZipFile(out).read("Monkey SMP Season I/READ ME.txt").decode()
    assert "version 2.5.0" in readme and "saves/Monkey SMP Season I/level.dat" in readme
    assert "/function realms:events/season/unlock" in readme   # the world was locked before the backup


def test_download_wants_a_world_folder(tmp_path):
    with pytest.raises(SystemExit, match="level.dat"):
        season.main(["download", str(tmp_path), "--season", "I", "--modpack", "2.5.0",
                     "--out", str(tmp_path / "s.zip")])
