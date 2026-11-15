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
    # 26.2 leaves Score out when it is 0 (the writer does too): it reads as 0, not as missing.
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
    folder = (FakeWorld(tmp_path).border(OVERWORLD, -80.0, 416.0, 5000.0, 5500.0)
              .border(NETHER, -9.5, 52.5, 625.0).path)
    assert saved_world.border(folder) == saved_world.SavedBorder(-80.0, 416.0, 5000.0, 5500.0)   # Overworld default
    assert saved_world.border(folder, NETHER) == saved_world.SavedBorder(-9.5, 52.5, 625.0, 625.0)
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


def test_names_are_one_rule_for_the_usercache(tmp_path):
    """staff_report kept the uuid's case and standings didn't check the name: a name the Rule check looked up by the
    stats file's lowercase uuid could go missing. Now every reader gets this."""
    import json
    (tmp_path / "usercache.json").write_text(json.dumps([
        {"uuid": "ABCDEF01-0000-4000-8000-000000000001", "name": "Alpha"},     # uppercase: kept, lowercased
        {"uuid": "00000002-0000-4000-8000-000000000002", "name": "Br@vo"},     # not a player's name
        {"uuid": "not-a-uuid", "name": "Carol"},
        {"name": "NoUuid"}, "junk"]))
    assert saved_world.names(tmp_path) == {"abcdef01-0000-4000-8000-000000000001": "Alpha"}
    (tmp_path / "usercache.json").write_text("{not json")
    assert saved_world.names(tmp_path) == {} and saved_world.names(tmp_path / "missing") == {}


@pytest.mark.parametrize(("stats", "ticks"), [
    ({"stats": {"minecraft:custom": {"minecraft:play_time": 72000}}}, 72000),
    ({"stats": {"minecraft:custom": {"minecraft:play_time": -1}}}, None),
    ({"stats": {"minecraft:custom": {"minecraft:play_time": True}}}, None),
    ({"stats": {}}, None), ([], None),
])
def test_play_time_reads_a_stats_file(tmp_path, stats, ticks):
    import json
    path = tmp_path / "u.json"
    path.write_text(json.dumps(stats))
    assert saved_world.play_time(path) == ticks
    assert saved_world.play_time(tmp_path / "missing.json") is None


def test_an_unreadable_party_file_stops_standings_but_the_rule_check_skips_it(tmp_path):
    world = FakeWorld(tmp_path).party("good", member("00000001-0000-4000-8000-000000000001", "Alpha"))
    (world.path / saved_world.PARTIES / "bad.nbt").write_bytes(b"not nbt")
    with pytest.raises(ValueError):
        saved_world.parties(world.path)
    found = saved_world.parties(world.path, lenient=True)
    assert [p.id for p in found] == ["good"]


def test_the_rule_check_keeps_every_member_it_can_read_and_reads_no_party_name(tmp_path, monkeypatch):
    """One bad member entry used to drop the whole party for the Rule check, so its members became strangers; and
    the party name (TOML, which needs Python 3.11) is never read when the caller doesn't show it."""
    alpha, bravo = "00000001-0000-4000-8000-000000000001", "00000002-0000-4000-8000-000000000002"
    world = FakeWorld(tmp_path).party("p", member(alpha, "Alpha"), [member(bravo, "Bravo"),
                                                                     {"uuid": "bad", "username": "Carol"}])
    with pytest.raises(ValueError):
        saved_world.parties(world.path)                              # standings: stops, as it always has
    monkeypatch.setattr(saved_world, "party_name", lambda *a: pytest.fail("read a party name"))
    [party] = saved_world.parties(world.path, lenient=True, named=False)
    assert [(m.uuid, m.username) for m in party.members] == [(alpha, "Alpha"), (bravo, "Bravo"), ("", "Carol")]
    assert party.owner.username == "Alpha" and party.name == ""


@pytest.mark.parametrize("config", ['playerConfig = "x"', "[playerConfig]\nparties = 1",
                                    "[playerConfig.parties]\nname = 3"])
def test_a_party_name_from_a_badly_shaped_config_is_none(tmp_path, config):
    owner = "00000001-0000-4000-8000-000000000001"
    path = tmp_path / saved_world.PLAYER_CONFIGS / f"{owner}.toml"
    path.parent.mkdir(parents=True)
    path.write_text(config)
    assert saved_world.party_name(tmp_path, owner) == ""


# ---------------------------------------------------------------- the server's player lists


def test_a_player_list_missing_is_empty_and_one_that_cant_be_read_is_none(tmp_path):
    import json
    assert saved_world.player_list(tmp_path, "whitelist") == []
    for broken in ("[{not json", json.dumps({"name": "Alpha"})):
        (tmp_path / "whitelist.json").write_text(broken)
        assert saved_world.player_list(tmp_path, "whitelist") is None          # can't tell, never "not listed"
    with pytest.raises(ValueError, match="not a player list"):
        saved_world.player_list(tmp_path, "usercache")
    (tmp_path / "ops.json").write_text(json.dumps([{"uuid": ALEX, "name": "Alex"}]))
    lists, unreadable = saved_world.player_lists(tmp_path)
    assert lists == {"whitelist": [], "ops": [{"uuid": ALEX, "name": "Alex"}], "banned-players": []}
    assert unreadable == ["whitelist.json"]


def test_a_player_list_keeps_entries_shaped_as_saved_and_matches_any_case(tmp_path):
    import json
    (tmp_path / "ops.json").write_text(json.dumps([
        {"uuid": ALEX.upper(), "name": "Alex", "level": 4},     # an uppercase uuid: kept, lowercased
        {"uuid": 7, "name": "Sam"},                             # a uuid that isn't text: ""
        {"uuid": RIA, "name": None}, {"uuid": RIA}, "junk", 3]))
    ops = saved_world.player_list(tmp_path, "ops")
    assert ops == [{"uuid": ALEX, "name": "Alex", "level": 4}, {"uuid": "", "name": "Sam"}]
    assert saved_world.list_entry(ops, "aLeX")["level"] == 4                        # no uuid known: by name
    assert saved_world.list_entry(ops, "whoever", ALEX.upper())["name"] == "Alex"   # by uuid, any case
    assert saved_world.list_entry(ops, "sam", SAM)["name"] == "Sam"                 # an entry with no uuid: by name
    assert saved_world.list_entry(ops, "Nobody") is None and saved_world.list_entry(ops, "Ria", RIA) is None
    (tmp_path / "banned-ips.json").write_text(json.dumps([{"ip": "8.8.8.8"}, {"ip": 8}, {"name": "x"}, "y"]))
    assert saved_world.player_list(tmp_path, "banned-ips") == [{"ip": "8.8.8.8"}]


def test_a_player_who_took_someones_old_name_is_not_on_their_lists(tmp_path):
    """Matching by name or uuid marked the new holder of a name as banned, an operator or whitelisted."""
    import json
    (tmp_path / "banned-players.json").write_text(json.dumps([{"uuid": ALEX, "name": "Alex", "reason": "griefing"}]))
    bans = saved_world.player_list(tmp_path, "banned-players")
    assert saved_world.list_entry(bans, "Alex", RIA) is None                    # Ria is called Alex now: not banned
    assert saved_world.list_entry(bans, "Ria", ALEX)["reason"] == "griefing"    # the banned one, renamed: still
