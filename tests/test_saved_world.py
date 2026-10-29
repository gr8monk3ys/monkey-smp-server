import re
import struct
import tomllib
import uuid

import pytest
from fake_world import OVERWORLD, FakeWorld, member, toml_string, uuid_ints
from nbt_writer import Long, nbt

import saved_world

ALEX, SAM, RIA = (str(uuid.uuid5(uuid.NAMESPACE_DNS, n)) for n in ("AlexFake", "SamFake", "RiaFake"))
NETHER = "minecraft:the_nether"


def names_file(tmp_path, rel: str) -> str:
    """The message a ValueError naming tmp_path/rel matches."""
    return re.escape(str(tmp_path / rel))


# ---------------------------------------------------------------- the scoreboard


def test_scores_by_objective_and_holder_a_missing_score_is_0(tmp_path):
    folder = FakeWorld(tmp_path).scores(("ev.cup", "red", 30), ("ev.cup", "blue", 0), ("rw.days", "AlexFake", 41),
                                        ("ev.cup", "#total", 99, {"Locked": 1})).path
    board = saved_world.scoreboard(folder)
    # 26.3 leaves Score out when it is 0 (the writer does too): it reads as 0, not as missing.
    assert board.scores == {"ev.cup": {"red": 30, "blue": 0, "#total": 99}, "rw.days": {"AlexFake": 41}}


def test_a_holder_saved_twice_keeps_the_later_score(tmp_path):
    board = saved_world.scoreboard(FakeWorld(tmp_path).scores(("ev.cup", "red", 3), ("ev.cup", "red", 5)).path)
    assert board.scores == {"ev.cup": {"red": 5}}


def test_display_names_are_plain_text_from_either_key_and_any_component(tmp_path):
    folder = FakeWorld(tmp_path).scores(
        ("ev.cup", "red", 30, {"display": "Red Monkeys"}),
        ("ev.cup", "blue", 10, {"display": {"text": "Blue", "extra": [" Herons"]}}),
        ("ev.cup", "green", 5, {"Display": [{"text": " Green"}, {"text": "Team "}]}),
        ("ev.cup", "grey", 1, {"display": ""}),
        ("st.kills", "AlexFake", 7)).path
    assert saved_world.scoreboard(folder).displays == {
        "ev.cup": {"red": "Red Monkeys", "blue": "Blue Herons", "green": " GreenTeam "}}


def test_a_scoreboard_not_under_data_still_reads(tmp_path):
    # Older saves had no "data" wrapper; the reader takes either.
    folder = FakeWorld(tmp_path).scoreboard({"PlayerScores": [{"Objective": "ev.cup", "Name": "red", "Score": 2}]}).path
    assert saved_world.scoreboard(folder).scores == {"ev.cup": {"red": 2}}


def test_teams(tmp_path):
    folder = FakeWorld(tmp_path).scores(teams=[
        {"Name": "tier_banner", "DisplayName": "tier_banner", "TeamColor": "green", "Players": ["AlexFake"]},
        {"Name": "champion", "MemberNamePrefix": {"text": "[S1 Champion] ", "color": "gold"},
         "MemberNameSuffix": "!", "Players": ["SamFake", "RiaFake"]},
        {"Name": "empty"}]).path
    assert saved_world.scoreboard(folder).teams == [
        saved_world.Team("tier_banner", "green", None, None, ["AlexFake"]),
        saved_world.Team("champion", "", {"text": "[S1 Champion] ", "color": "gold"}, "!", ["SamFake", "RiaFake"]),
        saved_world.Team("empty")]


def test_an_empty_scoreboard_and_no_scoreboard(tmp_path):
    board = saved_world.scoreboard(FakeWorld(tmp_path / "a").scoreboard({"DataVersion": 5023, "data": {}}).path)
    assert board == saved_world.Scoreboard({}, {}, [])
    assert saved_world.scoreboard(tmp_path / "b") is None
    assert saved_world.scoreboard_path(tmp_path / "b") == tmp_path / "b" / "data" / "minecraft" / "scoreboard.dat"


def test_a_damaged_file_is_a_value_error_naming_it(tmp_path):
    FakeWorld(tmp_path)._write("data/minecraft/scoreboard.dat", b"not nbt")
    with pytest.raises(ValueError, match=names_file(tmp_path, "data/minecraft/scoreboard.dat")):
        saved_world.scoreboard(tmp_path)


@pytest.mark.parametrize("data", [
    {"PlayerScores": [{"Name": "red", "Score": 1}]},                       # no Objective
    {"PlayerScores": [{"Objective": "ev.cup", "Score": 1}]},               # no Name
    {"PlayerScores": ["ev.cup"]},                                          # an entry that isn't a compound
    {"Teams": [{"Name": "t", "Players": 3}]},                              # Players that isn't a list
])
def test_a_scoreboard_not_shaped_as_saved_is_a_value_error_naming_it(tmp_path, data):
    FakeWorld(tmp_path).scoreboard({"DataVersion": 5023, "data": data})
    with pytest.raises(ValueError, match=names_file(tmp_path, "data/minecraft/scoreboard.dat")):
        saved_world.scoreboard(tmp_path)


# ---------------------------------------------------------------- parties


def test_parties_owner_first_each_member_once_with_the_name_set(tmp_path):
    folder = (FakeWorld(tmp_path)
              .party("p-red", member(ALEX, "AlexFake"), [member(SAM, "OldSam"), member(ALEX, "Again")])
              .party("p-blue", member(RIA), [member(SAM, "")])
              .party_name(ALEX, "  Red Monkeys ").path)
    red, blue = sorted(saved_world.parties(folder), key=lambda p: p.id, reverse=True)
    assert red == saved_world.Party("p-red", saved_world.Member(ALEX, "AlexFake"),
                                    [saved_world.Member(ALEX, "AlexFake"), saved_world.Member(SAM, "OldSam")],
                                    "Red Monkeys")
    assert blue.members == [saved_world.Member(RIA, ""), saved_world.Member(SAM, "")] and blue.name == ""


def test_a_party_name_with_quotes_and_backslashes(tmp_path):
    name = 'The "Real" \\Monkeys\\'
    assert tomllib.loads(f"name = {toml_string(name)}")["name"] == name
    folder = FakeWorld(tmp_path).party("p", member(ALEX, "AlexFake")).party_name(ALEX, name).path
    assert saved_world.parties(folder)[0].name == name


def test_a_party_without_an_owner_is_listed_with_none(tmp_path):
    folder = FakeWorld(tmp_path).party("p-ghost", None, [member(SAM, "SamFake")]).path
    assert saved_world.parties(folder) == [saved_world.Party("p-ghost", None, [], "")]


def test_an_unreadable_party_name_is_no_name(tmp_path):
    folder = FakeWorld(tmp_path).party("p", member(ALEX, "AlexFake")).path
    (folder / "data/openpartiesandclaims/player-configs").mkdir(parents=True)
    (folder / f"data/openpartiesandclaims/player-configs/{ALEX}.toml").write_text("not = [toml")
    assert saved_world.parties(folder)[0].name == ""
    assert saved_world.party_name(folder, SAM) == ""   # no config at all


def test_no_parties_folder_is_none_an_empty_one_no_parties(tmp_path):
    assert saved_world.parties(tmp_path) is None
    (tmp_path / "data/openpartiesandclaims/parties").mkdir(parents=True)
    assert saved_world.parties(tmp_path) == []


@pytest.mark.parametrize("bad", [
    {"uuid": "not-a-uuid", "rank": "MEMBER"},                    # text that isn't a UUID
    {"uuid": [Long(1), Long(2), Long(3)], "rank": "MEMBER"},     # three numbers
    {"uuid": ["a", "b", "c", "d"], "rank": "MEMBER"},            # four that aren't ints (struct.error)
    {"rank": "MEMBER"},                                          # no uuid at all
])
def test_a_party_file_with_a_bad_member_is_a_value_error_naming_it(tmp_path, bad):
    # standings stopped on one before saved_world.py too; now the error says which file.
    folder = FakeWorld(tmp_path).party("p-good", member(ALEX, "AlexFake")).party("p-bad", member(RIA), [bad]).path
    with pytest.raises(ValueError, match=names_file(tmp_path, "data/openpartiesandclaims/parties/p-bad.nbt")):
        saved_world.parties(folder)


# ---------------------------------------------------------------- claims


def test_claims_per_file_in_one_dimension_in_order_saved(tmp_path):
    folder = (FakeWorld(tmp_path).claims(ALEX, {OVERWORLD: [(3, 4), (-1, 2), (3, 4)], NETHER: [(0, 0)]})
              .claims("server-claims", {OVERWORLD: [(0, 1)]}).path)
    # Two claims in one dimension: their chunks run on.
    path = folder / f"data/openpartiesandclaims/player-claims/{SAM}.nbt"
    path.write_bytes(nbt({"dimensions": {OVERWORLD: {"claims": [{"positions": [{"x": 1, "z": 1}]},
                                                                {"positions": [{"x": 2, "z": 2}]}, {}]}}}))
    assert saved_world.claims(folder, OVERWORLD) == {
        ALEX: [(3, 4), (-1, 2), (3, 4)], SAM: [(1, 1), (2, 2)], "server-claims": [(0, 1)]}
    assert saved_world.claims(folder, NETHER) == {ALEX: [(0, 0)], SAM: [], "server-claims": []}
    assert saved_world.claim_counts(folder) == {ALEX: 4, SAM: 2, "server-claims": 1}


def test_no_claims(tmp_path):
    assert saved_world.claims(tmp_path, OVERWORLD) == {} and saved_world.claim_counts(tmp_path) == {}
    (tmp_path / "data/openpartiesandclaims/player-claims").mkdir(parents=True)
    (tmp_path / f"data/openpartiesandclaims/player-claims/{ALEX}.nbt").write_bytes(nbt({"username": "x"}))
    assert saved_world.claims(tmp_path, OVERWORLD) == {ALEX: []}
    assert saved_world.claim_counts(tmp_path) == {ALEX: 0}


def bad_nether_claim(tmp_path):
    """A world whose one claims file has a fine Overworld claim and a Nether position with no x or z."""
    folder = FakeWorld(tmp_path).claims(ALEX, {OVERWORLD: [(3, 4)]}).path
    path = folder / f"data/openpartiesandclaims/player-claims/{ALEX}.nbt"
    path.write_bytes(nbt({"dimensions": {OVERWORLD: {"claims": [{"positions": [{"x": 3, "z": 4}]}]},
                                         NETHER: {"claims": [{"positions": [{"y": 1}]}]}}}))
    return folder


def test_a_bad_claim_in_another_dimension_is_not_read(tmp_path):
    folder = bad_nether_claim(tmp_path)
    assert saved_world.claims(folder, OVERWORLD) == {ALEX: [(3, 4)]}
    assert saved_world.claim_counts(folder) == {ALEX: 2}   # counted, not read
    with pytest.raises(ValueError, match=names_file(tmp_path, f"data/openpartiesandclaims/player-claims/{ALEX}.nbt")):
        saved_world.claims(folder, NETHER)


def test_claims_not_shaped_as_saved_are_a_value_error_naming_the_file(tmp_path):
    rel = f"data/openpartiesandclaims/player-claims/{ALEX}.nbt"
    FakeWorld(tmp_path)._write(rel, nbt({"dimensions": [1, 2]}))
    for read in (lambda: saved_world.claims(tmp_path, OVERWORLD), lambda: saved_world.claim_counts(tmp_path)):
        with pytest.raises(ValueError, match=names_file(tmp_path, rel)):
            read()


def test_uuids_read_however_minecraft_saved_them():
    longs = [Long(v) for v in struct.unpack(">2q", uuid.UUID(ALEX).bytes)]
    for saved in (uuid_ints(ALEX), longs, ALEX.upper(), ALEX.replace("-", "")):
        assert saved_world.uuid_text(saved) == ALEX


@pytest.mark.parametrize("value", ["server-claims", ["a", "b", "c", "d"], [1.5, 2.5]])
def test_a_uuid_that_is_not_one_is_a_value_error(value):
    with pytest.raises(ValueError):
        saved_world.uuid_text(value)


# ---------------------------------------------------------------- the border


def test_the_border_as_saved_per_dimension(tmp_path):
    folder = (FakeWorld(tmp_path).border(OVERWORLD, -80.0, 416.0, 2500.0, 4000.0)
              .border(NETHER, -9.5, 52.5, 312.5).path)
    assert saved_world.border(folder) == saved_world.SavedBorder(-80.0, 416.0, 2500.0, 4000.0)   # Overworld default
    assert saved_world.border(folder, NETHER) == saved_world.SavedBorder(-9.5, 52.5, 312.5, 312.5)
    assert saved_world.border(folder, "minecraft:the_end") is None
    nether = folder / "dimensions" / "minecraft" / "the_nether" / "data" / "minecraft" / "world_border.dat"
    assert saved_world.border_path(folder, NETHER) == nether


def test_a_border_without_lerp_target_is_not_moving(tmp_path):
    FakeWorld(tmp_path)._write("dimensions/minecraft/overworld/data/minecraft/world_border.dat",
                               nbt({"data": {"center_x": 0.0, "center_z": 0.0, "size": 100.0}}, gzipped=True))
    assert saved_world.border(tmp_path) == saved_world.SavedBorder(0.0, 0.0, 100.0, 100.0)


@pytest.mark.parametrize("root", [{"center_x": 0.0}, {"data": {"center_x": 0.0, "size": 100.0}}, {"data": 3}])
def test_a_border_not_shaped_as_saved_is_a_value_error_naming_it(tmp_path, root):
    rel = "dimensions/minecraft/overworld/data/minecraft/world_border.dat"
    FakeWorld(tmp_path)._write(rel, nbt(root, gzipped=True))
    with pytest.raises(ValueError, match=names_file(tmp_path, rel)):
        saved_world.border(tmp_path)
