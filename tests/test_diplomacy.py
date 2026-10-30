"""Factions in game and war and pacts (tools/diplomacy.py), and what standings does with them."""
import copy
import datetime as dt
import json
import re

import pytest
from fake_world import score_rows
from nbt_writer import nbt
from test_standings import BASELINE, SCOREBOARD, SUNDAY, WEBHOOK, FakeDiscord, make_world

import datapacks
import diplomacy
import rcon
import standings

FILES = diplomacy.datapack_files()
FN = diplomacy.FN


def fn(path: str) -> str:
    return FILES[f"{FN}/{path}.mcfunction"]


def storage(world, contents: dict) -> None:
    """The monkey namespace's command storage, laid out as a 26.3 server saves it (data/monkey/command_storage.dat,
    gzipped, the paths under data.contents)."""
    path = world / "data" / "monkey" / "command_storage.dat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(nbt({"DataVersion": 5023, "data": {"contents": contents}}, gzipped=True))


def with_scores(*rows):
    board = copy.deepcopy(SCOREBOARD)
    board["data"]["PlayerScores"].extend(score_rows(*rows))
    return board


FACTIONS = [diplomacy.Faction("p-red", "Red Monkeys", ["AlexFake", "SamFake"]),
            diplomacy.Faction("p-blue", "Blue Herons", ["RiaFake", "TomFake"])]


# ---------------------------------------------------------------- the numbers in game


def C(f, **args):   # noqa: N802 (reads like the change it is)
    return {"f": f, **args}


def test_a_first_sync_numbers_every_faction_in_party_id_order():
    assert diplomacy.sync_changes(FACTIONS, {}, {}) == [
        C("sync/id", n=2, v="p-red"), C("sync/name", n=2, v="Red Monkeys"),
        C("sync/id", n=1, v="p-blue"), C("sync/name", n=1, v="Blue Herons"),
        C("sync/set", p="AlexFake", o="st.faction", v=2), C("sync/set", p="RiaFake", o="st.faction", v=1),
        C("sync/set", p="SamFake", o="st.faction", v=2), C("sync/set", p="TomFake", o="st.faction", v=1),
        C("sync/set", p="AlexFake", o="st.leader", v=1),   # the owner, first in the party
        C("sync/set", p="RiaFake", o="st.leader", v=1),
    ]


SAVED = {"factions": {"ids": {"f1": "p-blue", "f2": "p-red", "f3": "p-gone"},
                      "names": {"f1": {"text": "Blue Herons"}, "f2": {"text": "Red Monkeys"},
                                "f3": {"text": "Gone Faction"}}}}
SCORES = {"st.faction": {"AlexFake": 2, "SamFake": 2, "RiaFake": 1, "TomFake": 1, "OldName": 3, "#x": 9},
          "st.leader": {"AlexFake": 1, "RiaFake": 1, "OldName": 1}}


def missing(*numbers):
    return {**SAVED, "diplomacy": {"missing": {f"f{n}": 1 for n in numbers}}}


def test_a_sync_sends_only_what_changed_and_never_reuses_a_number():
    # Faction 3 is missing from this read: marked, and its player keeps the number until the next run.
    warned = []
    assert diplomacy.sync_changes(FACTIONS, SCORES, SAVED, warned.append) == [C("sync/missing", n=3)]
    assert "missing from the parties read" in warned[0]
    # Still missing on the next run: gone (its number stays given), and its player's scores go.
    assert diplomacy.sync_changes(FACTIONS, SCORES, missing(3)) == [
        C("sync/gone", n=3), C("sync/reset", p="OldName", o="st.faction"), C("sync/reset", p="OldName", o="st.leader")]
    # Back on the next run (a bad read): nothing ended, and the mark goes.
    back = [*FACTIONS, diplomacy.Faction("p-gone", "Gone Faction", ["OldName"])]
    assert diplomacy.sync_changes(back, SCORES, missing(3)) == [C("sync/found", n=3)]
    # A pact or war with a faction that is gone ends first, while its name can still be announced. A war's
    # score is its declaration's number.
    at_odds = {**SCORES, "dp.pact": {"#2.3": 1, "#1.2": 1}, "dp.war": {"#1.3": 17}}
    assert diplomacy.sync_changes(FACTIONS, at_odds, missing(3))[:3] == [
        C("dissolve", a=1, b=3), C("dissolve", a=2, b=3), C("sync/gone", n=3)]
    assert "dissolve_pair with storage monkey:diplomacy pair" in fn("dissolve")
    # Sam leaves Red and makes a party of his own; Blue is renamed; Tom becomes Blue's owner.
    now = [diplomacy.Faction("p-red", "Red Monkeys", ["AlexFake"]),
           diplomacy.Faction("p-blue", "Blue Herons Two", ["TomFake", "RiaFake"]),
           diplomacy.Faction("p-sam", "Sams Band", ["SamFake"]),
           diplomacy.Faction("p-gone", "Gone Faction", ["OldName"])]
    changes = diplomacy.sync_changes(now, SCORES, SAVED)
    assert C("sync/id", n=4, v="p-sam") in changes   # not 3, nor 1 or 2
    assert C("sync/name", n=1, v="Blue Herons Two") in changes
    assert C("sync/set", p="SamFake", o="st.faction", v=4) in changes
    assert C("sync/set", p="TomFake", o="st.leader", v=1) in changes
    assert C("sync/reset", p="RiaFake", o="st.leader") in changes
    assert C("sync/set", p="SamFake", o="st.leader", v=1) in changes
    assert not any("#x" in json.dumps(c) for c in changes)   # a fake player's score is never touched


def test_a_read_that_cant_be_trusted_ends_no_faction():
    # No parties read at all (the folder missing or unreadable): nothing is sent, nothing ends.
    warned = []
    assert diplomacy.sync_changes([], SCORES, missing(1, 2, 3), warned.append) == []
    assert "can't tell" in warned[0]
    # A party file that can't be read (no owner) keeps its number, name and players, even marked missing.
    assert diplomacy.sync_changes(FACTIONS[:1], SCORES, missing(1), unsure=frozenset({"p-blue", "p-gone"})) == [
        C("sync/found", n=1)]
    # The first run with a good read never ends a faction, whatever is missing.
    assert not [c for c in diplomacy.sync_changes(FACTIONS[:1], {**SCORES, "dp.pact": {"#1.2": 1}}, SAVED)
                if c["f"] in ("dissolve", "sync/gone")]


def test_numbers_run_out_with_a_warning_and_a_bad_name_is_left_out():
    taken = {"ids": {f"f{n}": f"p-{n:03}" for n in range(1, diplomacy.MAX_FACTIONS + 1)}}
    warned = []
    late = [diplomacy.Faction("p-zzz", "Late", ["Late_One", "not a name;say hi"])]
    assert diplomacy.sync_changes(late, {}, {"factions": taken}, warned.append) == []
    assert "no faction number left" in warned[0]
    warned.clear()
    changes = diplomacy.sync_changes(late, {}, {}, warned.append)
    assert C("sync/set", p="Late_One", o="st.faction", v=1) in changes
    assert not any("say" in json.dumps(c) for c in changes) and "not a player name" in warned[0]


def test_changes_go_many_to_a_command_and_each_has_its_function():
    changes = diplomacy.sync_changes(
        [diplomacy.Faction(f"p-{i:03}", f"Faction {i}", [f"Player_{i}_{j}" for j in range(4)]) for i in range(40)],
        {}, {})
    assert len(changes) == 40 * 2 + 40 * 4 + 40
    commands = diplomacy.batch_commands(changes)
    assert len(commands) <= len(changes) / 10   # a first sync of 40 full factions: a few dozen commands, not 280
    for store, run in zip(commands[::2], commands[1::2], strict=True):
        assert store.startswith("data modify storage monkey:diplomacy batch set value [{f:")
        assert len(store.encode()) <= rcon.LIMIT and store.isascii()
        assert run == "function monkey:diplomacy/batch/run"
    assert sum(c.count("{f:") for c in commands) == len(changes)   # all of them, in order
    assert diplomacy.batch_commands([C("sync/name", n=1, v='Odd "name"')]) == [
        'data modify storage monkey:diplomacy batch set value [{f:"sync/name",n:1,v:"Odd \\"name\\""}]',
        "function monkey:diplomacy/batch/run"]
    # every function a change names exists, and batch/run makes them in order
    for f in {c["f"] for c in changes} | {"dissolve", "sync/gone", "sync/missing", "sync/found", "sync/reset",
                                          "war_over", "offer_over", "week_over"}:
        assert f"{FN}/{f}.mcfunction" in FILES, f
    assert fn("batch/one").strip() == "$function monkey:diplomacy/$(f) with storage monkey:diplomacy batch[0]"
    run = fn("batch/run")
    assert run.index("batch/one with storage monkey:diplomacy batch[0]") < run.index(
        "data remove storage monkey:diplomacy batch[0]") < run.index("function monkey:diplomacy/batch/run")
    assert "$scoreboard players set $(p) $(o) $(v)" in fn("sync/set")
    assert "names.f$(n).text set from storage monkey:diplomacy batch[0].v" in fn("sync/name")


def test_numbers_and_names_read_the_saved_storage(tmp_path):
    world = tmp_path / "world"
    world.mkdir()
    assert diplomacy.saved_storage(world) == {} and diplomacy.numbers(world) == {}
    storage(world, {"factions": {"ids": {"f1": "p-blue", "f2": "p-red", "x": "odd"},
                                 "names": {"f2": {"text": "Red Monkeys"}}}, "standings": {"week": {"text": ""}}})
    assert diplomacy.numbers(world) == {"p-blue": 1, "p-red": 2}
    assert diplomacy.names(world) == {2: "Red Monkeys"}
    (world / "data" / "monkey" / "command_storage.dat").write_bytes(nbt({"data": {"contents": "no"}}))
    with pytest.raises(ValueError, match="command_storage.dat: not as the server saves it"):
        diplomacy.saved_storage(world)


def test_the_hourly_board_run_writes_the_factions_first(tmp_path, capsys):
    world = make_world(tmp_path)
    server = rcon.Recorder()
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 0
    first_board = next(i for i, c in enumerate(server.sent) if c.startswith("data modify storage monkey:standings"))
    synced = "".join(server.sent[:first_board])
    assert '{f:"sync/set",p:"AlexFake",o:"st.faction",v:3}' in synced   # p-blue 1, p-lone 2, p-red 3
    assert '{f:"sync/name",n:2,v:"LoneFake\'s faction"}' in synced
    assert server.sent[first_board - 1] == "function monkey:diplomacy/batch/run" and first_board == 2
    assert "factions in game: " in capsys.readouterr().out
    # Once the world has saved what was sent, the next hour sends nothing for the factions.
    storage(world, {"factions": {"ids": {"f1": "p-blue", "f2": "p-lone", "f3": "p-red"},
                                 "names": {"f1": "Blue Herons", "f2": "LoneFake's faction", "f3": "Red Monkeys"}}})
    board = with_scores(*[("st.faction", p, n) for p, n in (("AlexFake", 3), ("SamFake", 3), ("RiaFake", 1),
                                                             ("TomFake", 1), ("LoneFake", 2))],
                        *[("st.leader", p, 1) for p in ("AlexFake", "RiaFake", "LoneFake")])
    world = make_world(tmp_path / "again", board)
    storage(world, {"factions": {"ids": {"f1": "p-blue", "f2": "p-lone", "f3": "p-red"},
                                 "names": {"f1": "Blue Herons", "f2": "LoneFake's faction", "f3": "Red Monkeys"}}})
    server = rcon.Recorder()
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 0
    assert server.sent[0].startswith("data modify storage monkey:standings week")


def test_a_failed_sync_never_stops_the_board(tmp_path, capsys):
    # refused by the server
    world = make_world(tmp_path)
    server = rcon.Recorder({"function monkey:diplomacy/batch/run": "Unknown function monkey:diplomacy/batch/run"})
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 1
    assert "could not write the factions in game" in capsys.readouterr().err
    assert server.sent[-1] == "function monkey:standings/publish"
    # a damaged command storage file (cut short while saving)
    (world / "data" / "monkey").mkdir(parents=True)
    (world / "data" / "monkey" / "command_storage.dat").write_bytes(b"\x1f\x8b\x08\x00broken")
    server = rcon.Recorder()
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 1
    assert "command_storage.dat" in capsys.readouterr().err
    assert server.sent[-1] == "function monkey:standings/publish" and not any("batch" in c for c in server.sent)


# ---------------------------------------------------------------- the kills column


def test_a_war_kill_counts_twice_in_the_kills_column(tmp_path):
    board = with_scores(("st.warkills", "AlexFake", 3), ("st.warkills", "RiaFake", 1))
    data = standings.read_world(make_world(tmp_path, board))
    rows = {r.name: r for r in standings.table(data, BASELINE)}
    # Alex 7 - 5 kills this week, 3 of them of a war enemy; Sam 2; Ria 10 - 4, 1 of them a war kill
    assert rows["Red Monkeys"].kills == 2 + 2 + 3 and rows["Blue Herons"].kills == 6 + 1
    # The week's snapshot keeps war kills too, so only this week's count.
    week = standings.snapshot(data, SUNDAY)
    assert week["warkills"] == {"AlexFake": 3, "RiaFake": 1}
    assert {r.name: r.kills for r in standings.table(data, week)}["Red Monkeys"] == 0
    # A week begun before diplomacy has no war kills in its snapshot: every war kill since is this week's.
    assert "warkills" not in BASELINE


def test_no_diplomacy_objective_is_carried_into_the_next_season():
    # tools/season.py carries every rw.* score: the faction numbers and wars belong to one world.
    objectives = set(re.findall(r"scoreboard objectives add (\S+)", fn("load")))
    assert objectives >= {"st.faction", "st.leader", "st.warkills", "dp.war", "dp.pact"}
    assert not any(o.startswith("rw.") for o in objectives)


# ---------------------------------------------------------------- the Sunday report


LOG = [{"n": 4, "kind": "war", "a": 3, "b": 1}, {"n": 5, "kind": "offer", "a": 2, "b": 1},
       {"n": 6, "kind": "pact", "a": 1, "b": 2}, {"n": 7, "kind": "break", "a": 1, "b": 2},
       {"n": 3, "kind": "war", "a": 1, "b": 2}, {"n": 8, "kind": "peace", "a": 9, "b": 3}]
NAMES = {"f1": "Blue Herons", "f2": "Lone_*Wolf*", "f3": "Red Monkeys"}


def test_the_report_has_this_weeks_declarations_and_the_pacts_standing():
    got = diplomacy.report({"diplomacy": {"log": LOG}, "factions": {"names": NAMES}},
                           {"dp.pact": {"#1.3": 1, "#2.3": 0, "#4.5": 1}, "dp.state": {"#world": 77}},
                           {"diplomacy_seq": 3, "diplomacy_world": 77})
    assert got["diplomacy_seq"] == 8 and got["diplomacy_world"] == 77
    assert got["diplomacy"] == [
        "**War and pacts this week**",
        "- Red Monkeys declared war on Blue Herons",
        "- Blue Herons and Lone\\_\\*Wolf\\* made a pact",   # offers stay in game; Discord markup is escaped
        "- Blue Herons broke its pact with Lone\\_\\*Wolf\\*",
        "- Faction 9 and Red Monkeys made peace, and a pact",   # a faction that is gone keeps its number
        "Pacts standing: Blue Herons and Red Monkeys.",
        "Every war ends with the week: a leader can declare again in game with `/trigger diplomacy`.",
    ]


def test_a_faction_gone_by_the_close_keeps_its_name_in_the_post():
    # Play-tested 2026-10-30: a party deleted midweek was "faction 1" in the post. sync/gone keeps the name aside.
    gone = fn("sync/gone").splitlines()
    keep = "$data modify storage monkey:diplomacy gone.f$(n) set from storage monkey:factions names.f$(n)"
    assert gone.index(keep) < gone.index("$data remove storage monkey:factions names.f$(n)")
    got = diplomacy.report({"diplomacy": {"log": LOG, "gone": {"f9": {"text": "Gold_Lemurs"}, "f3": "Old Name"}},
                            "factions": {"names": NAMES}}, {}, {"diplomacy_seq": 7})
    assert got["diplomacy"][1] == "- Gold\\_Lemurs and Red Monkeys made peace, and a pact"   # a live name wins
    # A `gone` staff set to something else by mistake is left out: the close still runs.
    bad = diplomacy.report({"diplomacy": {"log": LOG, "gone": ["f9"]}, "factions": {"names": NAMES}}, {},
                           {"diplomacy_seq": 7})
    assert bad["diplomacy"][1] == "- Faction 9 and Red Monkeys made peace, and a pact"


def test_a_quiet_week_reports_nothing_and_a_new_world_starts_the_count_again():
    assert diplomacy.report({}, {}, {}) == {"diplomacy": [], "diplomacy_seq": 0, "diplomacy_world": None}
    here = {"dp.state": {"#world": 5}}
    assert diplomacy.report({"diplomacy": {"log": LOG}}, here, {"diplomacy_seq": 8})["diplomacy"] == []
    # A new season's world (another marker) numbers its log from 1 again: all of it is new, even past the old 8.
    log = [{"n": n, "kind": "war", "a": 1, "b": 2} for n in range(1, 13)]
    fresh = diplomacy.report({"diplomacy": {"log": log}}, {"dp.state": {"#world": 6}},
                             {"diplomacy_seq": 8, "diplomacy_world": 5})
    assert fresh["diplomacy"][1] == "- Faction 1 declared war on faction 2" and "- and 2 more" in fresh["diplomacy"]
    assert fresh["diplomacy_seq"] == 12 and fresh["diplomacy_world"] == 6
    many = [{"n": i, "kind": "war", "a": 1, "b": 2} for i in range(1, 30)]
    lines = diplomacy.report({"diplomacy": {"log": many}}, {}, {})["diplomacy"]
    assert len(lines) == 1 + diplomacy.REPORT_LIMIT + 2 and "- and 19 more" in lines


def test_a_read_that_cant_be_trusted_never_restarts_the_count():
    before = {"diplomacy_seq": 8, "diplomacy_world": 5}
    # The storage couldn't be read: nothing reported, and the count stays (next week reports this week's too).
    assert diplomacy.report(None, {"dp.state": {"#world": 5}}, before) == {
        "diplomacy": [], "diplomacy_seq": 8, "diplomacy_world": 5}
    # A trimmed or empty log in the same world is a quiet week, not a new world.
    assert diplomacy.report({"diplomacy": {"log": []}}, {"dp.state": {"#world": 5}}, before)["diplomacy_seq"] == 8
    assert diplomacy.report({}, {}, before)["diplomacy_seq"] == 8   # the marker not saved yet: can't tell


def test_the_pacts_line_and_the_post_have_a_cap():
    names = {f"f{n}": f"Faction Name {n:02}" for n in range(1, 41)}
    pacts = {f"#{n}.{n + 20}": 1 for n in range(1, 21)}
    lines = diplomacy.report({"factions": {"names": names}}, {"dp.pact": pacts}, {})["diplomacy"]
    assert lines[0].endswith(f"; and {20 - diplomacy.PACTS_LIMIT} more.") and lines[0].count(" and ") == 11
    # However long the week, the post fits Discord's 2000 and every code block is closed.
    long = [f"- {'X' * 150} declared war on {'Y' * 20}"] * 30
    week = {"start": None, "end": "2026-11-01T19:00:00-08:00", "rows": [], "diplomacy": long}
    message = standings.discord_message(week)
    assert len(message) <= standings.DISCORD_LIMIT and message.count("```") % 2 == 0
    assert diplomacy.MORE in message and message.rstrip().endswith("shows the board in game.")
    assert diplomacy.discord_lines({"diplomacy": ["a" * 10, "b" * 10]}, 22) == ["a" * 10, "b" * 10]
    assert diplomacy.discord_lines({"diplomacy": ["a" * 10, "b" * 10]}, 21) == []   # no room for MORE either
    more = len(diplomacy.MORE)
    assert diplomacy.discord_lines({"diplomacy": ["a" * 10, "b" * 10, "c" * more]}, 22 + more) == [
        "a" * 10, diplomacy.MORE]
    assert diplomacy.discord_lines({"diplomacy": ["a" * 10]}, 5) == []


def closing(tmp_path, board=None):
    world = make_world(tmp_path, board or with_scores(("dp.pact", "#1.3", 1), ("dp.war", "#1.2", 3),
                                                      ("dp.offer", "#2.1", 5), ("dp.state", "#world", 77)))
    storage(world, {"diplomacy": {"log": LOG}, "factions": {"names": NAMES}})
    state = tmp_path / "state"
    (state / "weeks").mkdir(parents=True)
    (state / "week.json").write_text(json.dumps(BASELINE))
    (state / "weeks" / "2026-10-25.json").write_text(json.dumps(
        {"start": None, "end": "2026-10-25T19:00:00-07:00", "rows": [], "announced": True, "posted": True,
         "diplomacy_seq": 3, "diplomacy_world": 77}))
    return world, state


def batched(sent) -> str:
    return "".join(c for c in sent if c.startswith("data modify storage monkey:diplomacy batch"))


def test_close_posts_the_week_of_war_and_ends_the_wars_once(tmp_path, capsys):
    world, state = closing(tmp_path)
    server, discord = rcon.Recorder(), FakeDiscord()
    assert standings.close(world, state, server, SUNDAY, WEBHOOK, discord) == 0
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["diplomacy_seq"] == 8 and closed["diplomacy_world"] == 77 and closed["wars_ended"]
    # the wars and offers running when the world was read, each by its declaration's number, then week_over
    assert closed["war_ends"] == [{"f": "war_over", "lo": 1, "hi": 2, "seq": 3},
                                  {"f": "offer_over", "a": 2, "b": 1, "seq": 5}, {"f": "week_over", "seq": 8}]
    assert server.sent.index("function monkey:standings/announce") < server.sent.index(
        "function monkey:diplomacy/batch/run")
    assert '{f:"war_over",lo:1,hi:2,seq:3}' in batched(server.sent)
    content = discord.posts[0][2]["content"]
    assert "- Red Monkeys declared war on Blue Herons" in content and len(content) <= standings.DISCORD_LIMIT
    assert content.index("```\n**War and pacts") < content.index("Scored as")
    # a retry closes nothing and ends no war twice
    assert standings.close(world, state, server, SUNDAY + dt.timedelta(minutes=5), WEBHOOK, discord) == 0
    assert batched(server.sent).count("week_over") == 1
    # the next week reports only what came after
    nxt = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert diplomacy.report({"diplomacy": {"log": LOG}}, {"dp.state": {"#world": 77}}, nxt)["diplomacy"] == []


def test_the_wars_end_even_when_the_board_fails_and_a_late_retry_ends_only_the_closed_weeks(tmp_path, capsys):
    world, state = closing(tmp_path)
    server = rcon.Recorder({"function monkey:standings/publish": "Unknown function monkey:standings/publish"})
    assert standings.close(world, state, server, SUNDAY, "", FakeDiscord()) == 1
    assert "could not update the in-game board" in capsys.readouterr().err
    assert "week_over" in batched(server.sent)   # the board's failure didn't keep the wars going
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["wars_ended"] and not closed["announced"]
    # The server was down for the wars' end too: a retry hours later, after a new war (seq 9) was declared in
    # the new week and saved, still sends only the closed week's own ends.
    world2, state2 = closing(tmp_path / "late")
    down = rcon.Recorder(fail=99)
    assert standings.close(world2, state2, down, SUNDAY, "", FakeDiscord()) == 1
    assert not json.loads((state2 / "weeks" / "2026-11-01.json").read_text())["wars_ended"]
    (world2 / "data" / "minecraft" / "scoreboard.dat").write_bytes(
        nbt(with_scores(("dp.war", "#1.2", 9)), gzipped=True))
    server = rcon.Recorder()
    assert standings.close(world2, state2, server, SUNDAY + dt.timedelta(hours=3), "", FakeDiscord()) == 0
    sent = batched(server.sent)
    assert '{f:"war_over",lo:1,hi:2,seq:3}' in sent and "seq:9" not in sent
    # and in game war_over ends a war only if it is still the one declared then
    over = fn("war_over")
    assert over.index("$execute unless score #$(lo).$(hi) dp.war matches $(seq) run return 0") < over.index(
        "$scoreboard players reset #$(lo).$(hi) dp.war")
    assert "$execute unless score #$(a).$(b) dp.offer matches $(seq) run return 0" in fn("offer_over")


def test_a_damaged_storage_file_never_stops_the_close(tmp_path, capsys):
    world, state = closing(tmp_path)
    (world / "data" / "monkey" / "command_storage.dat").write_bytes(b"\x1f\x8b\x08\x00cut short")
    server, discord = rcon.Recorder(), FakeDiscord()
    assert standings.close(world, state, server, SUNDAY, WEBHOOK, discord) == 0
    assert "left out of the post" in capsys.readouterr().err
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["diplomacy"] == [] and closed["diplomacy_seq"] == 3 and closed["posted"]
    assert '{f:"week_over",seq:3}' in batched(server.sent)   # the wars still end; the log keeps this week's


def test_a_week_closed_before_diplomacy_ends_no_war(tmp_path):
    # The last closed week has no wars_ended (it was closed by an older release): a re-run ends nothing.
    world = make_world(tmp_path)
    state = tmp_path / "state"
    (state / "weeks").mkdir(parents=True)
    (state / "week.json").write_text(json.dumps({**BASELINE, "start": "2026-10-31T19:00:00-07:00"}))
    (state / "weeks" / "2026-10-31.json").write_text(json.dumps(
        {"start": None, "end": "2026-10-31T19:00:00-07:00", "rows": [], "announced": True, "posted": True}))
    server = rcon.Recorder()
    assert standings.close(world, state, server, SUNDAY, "", FakeDiscord()) == 0
    assert not batched(server.sent)


def test_week_over_counts_the_wars_that_ended_and_trims_the_log():
    assert "scoreboard players add #ended dp.state 1" in fn("war_over")
    over = fn("week_over")
    assert over.index("execute if score #ended dp.state matches 1.. run tellraw @a") < over.index(
        "scoreboard players set #ended dp.state 0")
    assert "#wars" not in "".join(FILES.values())   # peace, staff and a gone faction end wars without a count
    assert "$scoreboard players set #trim dp.tmp $(seq)" in over and "function monkey:diplomacy/trim" in over
    trim = fn("trim")
    assert trim.index("if score #n dp.tmp > #trim dp.tmp run return 0") < trim.index(
        "data remove storage monkey:diplomacy log[0]") < trim.index("function monkey:diplomacy/trim")
    assert "dp.pact" not in over and "dp.pact" not in fn("war_over")   # pacts stand


# ---------------------------------------------------------------- the data pack


def test_the_pack_has_no_problems_with_the_standings_pack():
    # with every other pack, as they ship (#launched rw.day is the wardrobe's)
    assert [p for p in datapacks.problems(datapacks.all_files()) if "diplomacy" in p] == []
    tags = standings.datapack_files()
    assert "monkey:diplomacy/load" in tags["data/minecraft/tags/function/load.json"]
    assert "monkey:diplomacy/tick" in tags["data/minecraft/tags/function/tick.json"]


@pytest.mark.parametrize("n", [1, 42, diplomacy.MAX_FACTIONS])
def test_a_kill_advancement_per_faction_number(n):
    adv = json.loads(FILES[f"{diplomacy.ADVANCEMENT}/kill/f{n}.json"])
    criterion = adv["criteria"]["kill"]
    assert criterion["trigger"] == "minecraft:player_killed_entity"
    terms = criterion["conditions"]["entity"]["terms"]
    assert {"type": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:entity_type": "minecraft:player"}} in terms
    assert {"type": "minecraft:entity_scores", "entity": "this", "scores": {"st.faction": {"min": n, "max": n}}} \
        in terms
    assert '"condition"' not in json.dumps(adv)   # the pre-26 key fails the whole pack
    assert adv["rewards"] == {"function": f"monkey:diplomacy/kill/f{n}"}
    reward = fn(f"kill/f{n}").splitlines()
    assert reward[1] == f"advancement revoke @s only monkey:diplomacy/kill/f{n}"   # first, so the next kill fires
    assert reward[2] == f"function monkey:diplomacy/kill {{b:{n}}}"


def test_a_war_kill_counts_only_at_war_outside_the_arena_after_the_launch():
    kill = fn("kill")
    for gate in ("execute unless score #launched rw.day matches 1 run return 0",
                 "execute if entity @s[tag=ev.arena] run return 0",
                 "execute unless score @s st.faction matches 1.. run return 0"):
        assert kill.index(gate) < kill.index("function monkey:diplomacy/pair")
    war_kill = fn("war_kill").splitlines()
    assert war_kill[0] == "$execute unless score #$(lo).$(hi) dp.war matches 1.. run return 0"
    assert war_kill[1] == "scoreboard players add @s st.warkills 1"


def test_pair_puts_the_smaller_number_first():
    pair = fn("pair")
    assert "scoreboard players operation #lo dp.tmp < #b dp.tmp" in pair
    assert "scoreboard players operation #hi dp.tmp > #b dp.tmp" in pair


def test_only_an_owner_acts_and_only_after_the_launch():
    use = fn("use")
    order = ["unless score #launched rw.day matches 1", "unless score @s st.faction matches 1..",
             "run return run function monkey:diplomacy/menu", "unless score @s st.leader matches 1",
             "if score #a dp.tmp = #b dp.tmp", "unless function monkey:diplomacy/known",
             "if function monkey:diplomacy/cooling", "matches 1 run return run function monkey:diplomacy/war"]
    at = [use.index(s) for s in order]
    assert at == sorted(at)
    assert "matches ..9 run return run function monkey:diplomacy/menu" in use


@pytest.mark.parametrize("action", sorted(diplomacy.ACTIONS))
def test_a_button_decodes_to_its_faction_and_action(action):
    # The button sends "/trigger diplomacy set <N><action>"; use takes N = value / 10 and action = value % 10.
    value = int(f"{diplomacy.MAX_FACTIONS}{diplomacy.ACTIONS[action]}")
    assert value // 10 == diplomacy.MAX_FACTIONS and value % 10 == diplomacy.ACTIONS[action]
    assert 0 < diplomacy.ACTIONS[action] <= 9
    rows = "".join(fn(f"row/{i}") for i in range(len(diplomacy.ROWS)))
    assert f"/trigger diplomacy set $(b){diplomacy.ACTIONS[action]}" in rows


def test_no_war_with_a_pact_partner_and_a_pact_ends_a_war():
    war = fn("war")
    # the war's score is its declaration's number in the log (week_end ends that one and no later one)
    assert war.index("$execute if score #$(lo).$(hi) dp.pact matches 1 run return run") < war.index(
        '$function monkey:diplomacy/log {kind:"war",a:$(a),b:$(b)}') < war.index(
        "$scoreboard players operation #$(lo).$(hi) dp.war = #seq dp.state")
    assert fn("pact").index('$function monkey:diplomacy/log {kind:"offer",a:$(a),b:$(b)}') < fn("pact").index(
        "$scoreboard players operation #$(a).$(b) dp.offer = #seq dp.state")
    accept = fn("accept")
    assert "$scoreboard players reset #$(lo).$(hi) dp.war" in accept
    assert "$scoreboard players set #$(lo).$(hi) dp.pact 1" in accept
    # a faction holds at most MAX_PACTS, checked for both sides before an offer or an acceptance
    pact = fn("pact")
    for side in ("a", "b"):
        assert pact.index(f"$execute if score #f$({side}) dp.pacts matches {diplomacy.MAX_PACTS}..") < pact.index(
            "diplomacy/accept")


def test_every_declaration_is_announced_logged_and_cools_down():
    for name, kind in (("war", "war"), ("pact", "offer"), ("pact_made", "pact"), ("peace", "peace"),
                       ("break", "break"), ("staff/end_pair", "end")):
        body = fn(name)
        assert "$tellraw @a " in body, name
        assert f'$function monkey:diplomacy/log {{kind:"{kind}",a:$(a),b:$(b)}}' in body, name
    for name in ("war", "pact", "accept", "break"):
        assert "$execute store result score #f$(a) dp.last run time query gametime" in fn(name)
    # breaking a pact names the player who did it
    assert '{"selector":"@s"' in fn("break")
    assert f"matches 0..{diplomacy.COOLDOWN_SECONDS * 20 - 1} run return 1" in fn("cooling_of")


def test_the_week_end_ends_each_war_and_offer_running_at_the_close_but_no_pact():
    scores = {"dp.war": {"#1.2": 3, "#2.5": 0, "junk": 4}, "dp.offer": {"#3.1": 6}, "dp.pact": {"#1.3": 1}}
    assert diplomacy.week_end(scores, 9) == [C("war_over", lo=1, hi=2, seq=3), C("offer_over", a=3, b=1, seq=6),
                                              C("week_over", seq=9)]
    assert diplomacy.week_end({}, 0) == [C("week_over", seq=0)]


def test_staff_and_a_gone_faction_end_a_pair_the_same_way():
    end_pair = fn("end_pair")
    assert "$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(a) dp.pacts 1" \
        in end_pair and "$scoreboard players reset #$(lo).$(hi) dp.war" in end_pair
    for caller in ("staff/end_pair", "dissolve_pair"):
        assert "function monkey:diplomacy/end_pair with storage monkey:diplomacy pair" in fn(caller), caller
        assert "dp.pacts 1" not in fn(caller), caller


def test_a_world_is_marked_once_for_the_sunday_report():
    assert ("execute unless score #world dp.state matches 1.. store result score #world dp.state run random value "
            "1..2147483646") in fn("load")


def test_the_launch_clears_what_came_before_it_once():
    second = fn("second")
    assert ("execute if score #launched rw.day matches 1 unless score #launched dp.state matches 1 run function "
            "monkey:diplomacy/launch") in second
    launch = fn("launch")
    for o in ("dp.war", "dp.pact", "dp.offer", "dp.pacts", "st.warkills"):
        assert f"scoreboard players reset * {o}" in launch
    assert "scoreboard players set #ended dp.state 0" in launch
    assert launch.rstrip().endswith("scoreboard players set #launched dp.state 1")


def test_the_menu_lists_every_number_but_your_own():
    menu = fn("menu")
    assert menu.count("run function monkey:diplomacy/row {b:") == diplomacy.MAX_FACTIONS
    assert ("execute if data storage monkey:factions names.f7 unless score @s st.faction matches 7 run function "
            "monkey:diplomacy/row {b:7}") in menu
    for i in range(len(diplomacy.ROWS)):
        row = fn(f"row/{i}").splitlines()
        assert row[0].startswith("$execute if score @s st.leader matches 1 run return run tellraw @s ")
        assert "click_event" not in row[1]   # the buttons are only for the owner


def test_nothing_given_and_nothing_for_combat():
    for path, body in FILES.items():
        for line in body.splitlines():
            assert not re.match(r"\$?(give|effect|attribute|item |enchant|gamerule)", line), (path, line)


def test_help_lists_only_real_functions():
    assert fn("help").count("suggest_command") == len(diplomacy.HELP)
    for cmd, _ in diplomacy.HELP:
        assert f"{FN}/{cmd.split(' ')[0]}.mcfunction" in FILES

