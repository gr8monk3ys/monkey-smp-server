import re
import struct
import uuid

import pytest
from fake_world import OVERWORLD, FakeWorld, uuid_ints
from nbt_writer import Long, nbt

import world

ALEX, SAM, RIA = (str(uuid.uuid5(uuid.NAMESPACE_DNS, n)) for n in ("AlexFake", "SamFake", "RiaFake"))
NETHER = "minecraft:the_nether"


def person(u: str, username: str | None) -> dict:
    return {"uuid": uuid_ints(u), "rank": "MEMBER"} | ({"username": username} if username is not None else {})


# ---------------------------------------------------------------- the scoreboard


def test_scores_by_objective_and_holder_a_missing_score_is_0(tmp_path):
    folder = FakeWorld(tmp_path).scores(("ev.cup", "red", 30), ("ev.cup", "blue", 0), ("rw.days", "AlexFake", 41),
                                        ("ev.cup", "#total", 99, {"Locked": 1})).path
    board = world.scoreboard(folder)
    # 26.3 leaves Score out when it is 0 (the writer does too): it reads as 0, not as missing.
    assert board.scores == {"ev.cup": {"red": 30, "blue": 0, "#total": 99}, "rw.days": {"AlexFake": 41}}


def test_a_holder_saved_twice_keeps_the_later_score(tmp_path):
    board = world.scoreboard(FakeWorld(tmp_path).scores(("ev.cup", "red", 3), ("ev.cup", "red", 5)).path)
    assert board.scores == {"ev.cup": {"red": 5}}


def test_display_names_are_plain_text_from_either_key_and_any_component(tmp_path):
    folder = FakeWorld(tmp_path).scores(
        ("ev.cup", "red", 30, {"display": "Red Monkeys"}),
        ("ev.cup", "blue", 10, {"display": {"text": "Blue", "extra": [" Herons"]}}),
        ("ev.cup", "green", 5, {"Display": [{"text": " Green"}, {"text": "Team "}]}),
        ("ev.cup", "grey", 1, {"display": ""}),
        ("st.kills", "AlexFake", 7)).path
    assert world.scoreboard(folder).displays == {
        "ev.cup": {"red": "Red Monkeys", "blue": "Blue Herons", "green": " GreenTeam "}}


def test_a_scoreboard_not_under_data_still_reads(tmp_path):
    # Older saves had no "data" wrapper; the reader takes either.
    folder = FakeWorld(tmp_path).scoreboard({"PlayerScores": [{"Objective": "ev.cup", "Name": "red", "Score": 2}]}).path
    assert world.scoreboard(folder).scores == {"ev.cup": {"red": 2}}


def test_teams(tmp_path):
    folder = FakeWorld(tmp_path).scores(teams=[
        {"Name": "tier_banner", "DisplayName": "tier_banner", "TeamColor": "green", "Players": ["AlexFake"]},
        {"Name": "champion", "MemberNamePrefix": {"text": "[S1 Champion] ", "color": "gold"},
         "MemberNameSuffix": "!", "Players": ["SamFake", "RiaFake"]},
        {"Name": "empty"}]).path
    assert world.scoreboard(folder).teams == [
        world.Team("tier_banner", "green", None, None, ["AlexFake"]),
        world.Team("champion", "", {"text": "[S1 Champion] ", "color": "gold"}, "!", ["SamFake", "RiaFake"]),
        world.Team("empty")]


def test_an_empty_scoreboard_and_no_scoreboard(tmp_path):
    board = world.scoreboard(FakeWorld(tmp_path / "a").scoreboard({"DataVersion": 5023, "data": {}}).path)
    assert board == world.Scoreboard({}, {}, [])
    assert world.scoreboard(tmp_path / "b") is None
    assert world.scoreboard_path(tmp_path / "b") == tmp_path / "b" / "data" / "minecraft" / "scoreboard.dat"


def test_a_damaged_file_is_a_value_error_naming_it(tmp_path):
    fake = FakeWorld(tmp_path)
    fake._write("data/minecraft/scoreboard.dat", b"not nbt")
    with pytest.raises(ValueError, match=re.escape(str(world.scoreboard_path(tmp_path)))):
        world.scoreboard(tmp_path)


# ---------------------------------------------------------------- parties and claims


def test_parties_owner_first_each_member_once_with_the_name_set(tmp_path):
    folder = (FakeWorld(tmp_path)
              .party("p-red", person(ALEX, "AlexFake"), [person(SAM, "OldSam"), person(ALEX, "Again")])
              .party("p-blue", person(RIA, None), [person(SAM, "")])
              .party_name(ALEX, "  Red Monkeys ").path)
    red, blue = sorted(world.parties(folder), key=lambda p: p.id, reverse=True)
    assert red == world.Party("p-red", world.Member(ALEX, "AlexFake"),
                              [world.Member(ALEX, "AlexFake"), world.Member(SAM, "OldSam")], "Red Monkeys")
    assert blue.members == [world.Member(RIA, ""), world.Member(SAM, "")] and blue.name == ""


def test_a_party_without_an_owner_is_listed_with_none(tmp_path):
    folder = FakeWorld(tmp_path).party("p-ghost", None, [person(SAM, "SamFake")]).path
    assert world.parties(folder) == [world.Party("p-ghost", None, [], "")]


def test_an_unreadable_party_name_is_no_name(tmp_path):
    folder = FakeWorld(tmp_path).party("p", person(ALEX, "AlexFake")).path
    (folder / "data/openpartiesandclaims/player-configs").mkdir(parents=True)
    (folder / f"data/openpartiesandclaims/player-configs/{ALEX}.toml").write_text("not = [toml")
    assert world.parties(folder)[0].name == ""
    assert world.party_name(folder, SAM) == ""   # no config at all


def test_no_parties_folder_is_none_an_empty_one_no_parties(tmp_path):
    assert world.parties(tmp_path) is None
    (tmp_path / "data/openpartiesandclaims/parties").mkdir(parents=True)
    assert world.parties(tmp_path) == []


def test_claims_per_file_and_dimension_in_order_saved(tmp_path):
    folder = (FakeWorld(tmp_path).claims(ALEX, {OVERWORLD: [(3, 4), (-1, 2), (3, 4)], NETHER: [(0, 0)]})
              .claims("server-claims", {OVERWORLD: [(0, 1)]}).path)
    # Two claims in one dimension: their chunks run on.
    path = folder / f"data/openpartiesandclaims/player-claims/{SAM}.nbt"
    path.write_bytes(nbt({"dimensions": {OVERWORLD: {"claims": [{"positions": [{"x": 1, "z": 1}]},
                                                                {"positions": [{"x": 2, "z": 2}]}, {}]}}}))
    assert world.claims(folder) == {
        ALEX: {OVERWORLD: [(3, 4), (-1, 2), (3, 4)], NETHER: [(0, 0)]},
        SAM: {OVERWORLD: [(1, 1), (2, 2)]},
        "server-claims": {OVERWORLD: [(0, 1)]}}


def test_no_claims(tmp_path):
    assert world.claims(tmp_path) == {}
    (tmp_path / "data/openpartiesandclaims/player-claims").mkdir(parents=True)
    (tmp_path / f"data/openpartiesandclaims/player-claims/{ALEX}.nbt").write_bytes(nbt({"username": "x"}))
    assert world.claims(tmp_path) == {ALEX: {}}


def test_uuids_read_however_minecraft_saved_them():
    longs = [Long(v) for v in struct.unpack(">2q", uuid.UUID(ALEX).bytes)]
    for saved in (uuid_ints(ALEX), longs, ALEX.upper(), ALEX.replace("-", "")):
        assert world.uuid_text(saved) == ALEX


def test_a_uuid_that_is_not_one_is_a_value_error():
    with pytest.raises(ValueError):
        world.uuid_text("server-claims")


# ---------------------------------------------------------------- the border


def test_the_border_as_saved_per_dimension(tmp_path):
    folder = (FakeWorld(tmp_path).border(OVERWORLD, -80.0, 416.0, 2500.0, 4000.0)
              .border(NETHER, -9.5, 52.5, 312.5).path)
    assert world.border(folder) == world.SavedBorder(-80.0, 416.0, 2500.0, 4000.0)   # the Overworld by default
    assert world.border(folder, NETHER) == world.SavedBorder(-9.5, 52.5, 312.5, 312.5)
    assert world.border(folder, "minecraft:the_end") is None
    nether = folder / "dimensions" / "minecraft" / "the_nether" / "data" / "minecraft" / "world_border.dat"
    assert world.border_path(folder, NETHER) == nether


def test_a_border_without_lerp_target_is_not_moving(tmp_path):
    path = world.border_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(nbt({"data": {"center_x": 0.0, "center_z": 0.0, "size": 100.0}}, gzipped=True))
    assert world.border(tmp_path) == world.SavedBorder(0.0, 0.0, 100.0, 100.0)
