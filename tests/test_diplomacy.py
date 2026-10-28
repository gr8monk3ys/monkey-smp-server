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
    """The realms namespace's command storage, laid out as a 26.3 server saves it (data/realms/command_storage.dat,
    gzipped, the paths under data.contents)."""
    path = world / "data" / "realms" / "command_storage.dat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(nbt({"DataVersion": 5023, "data": {"contents": contents}}, gzipped=True))


def with_scores(*rows):
    board = copy.deepcopy(SCOREBOARD)
    board["data"]["PlayerScores"].extend(score_rows(*rows))
    return board


FACTIONS = [diplomacy.Faction("p-red", "Red Monkeys", ["AlexFake", "SamFake"]),
            diplomacy.Faction("p-blue", "Blue Herons", ["RiaFake", "TomFake"])]


# ---------------------------------------------------------------- the numbers in game


def test_a_first_sync_numbers_every_faction_in_party_id_order():
    commands = diplomacy.sync_commands(FACTIONS, {}, {})
    assert commands == [
        'data modify storage realms:factions ids.f2 set value "p-red"',
        'data modify storage realms:factions names.f2 set value {text:"Red Monkeys"}',
        'data modify storage realms:factions ids.f1 set value "p-blue"',
        'data modify storage realms:factions names.f1 set value {text:"Blue Herons"}',
        "scoreboard players set AlexFake st.faction 2",
        "scoreboard players set RiaFake st.faction 1",
        "scoreboard players set SamFake st.faction 2",
        "scoreboard players set TomFake st.faction 1",
        "scoreboard players set AlexFake st.leader 1",   # the owner, first in the party
        "scoreboard players set RiaFake st.leader 1",
    ]
    for c in commands:
        assert len(c.encode()) <= rcon.LIMIT and c.isascii()


def test_a_sync_sends_only_what_changed_and_never_reuses_a_number():
    saved = {"factions": {"ids": {"f1": "p-blue", "f2": "p-red", "f3": "p-gone"},
                          "names": {"f1": {"text": "Blue Herons"}, "f2": {"text": "Red Monkeys"},
                                    "f3": {"text": "Gone Faction"}}}}
    scores = {"st.faction": {"AlexFake": 2, "SamFake": 2, "RiaFake": 1, "TomFake": 1, "OldName": 3, "#x": 9},
              "st.leader": {"AlexFake": 1, "RiaFake": 1}}
    assert diplomacy.sync_commands(FACTIONS, scores, saved) == [
        "data remove storage realms:factions names.f3",      # the party is gone; its number stays given
        "scoreboard players reset OldName st.faction",
    ]
    # A pact or war with a faction that is gone ends first, while its name can still be announced.
    at_odds = {**scores, "dp.pact": {"#2.3": 1, "#1.2": 1}, "dp.war": {"#1.3": 1}}
    assert diplomacy.sync_commands(FACTIONS, at_odds, saved)[:3] == [
        "function realms:diplomacy/dissolve {a:1,b:3}", "function realms:diplomacy/dissolve {a:2,b:3}",
        "data remove storage realms:factions names.f3"]
    assert "dissolve_pair with storage realms:diplomacy pair" in fn("dissolve")
    assert "scoreboard players remove #f$(a) dp.pacts 1" in fn("dissolve_pair")
    # Sam leaves Red and makes a party of his own; Blue is renamed; Tom becomes Blue's owner.
    now = [diplomacy.Faction("p-red", "Red Monkeys", ["AlexFake"]),
           diplomacy.Faction("p-blue", "Blue Herons Two", ["TomFake", "RiaFake"]),
           diplomacy.Faction("p-sam", "Sams Band", ["SamFake"])]
    commands = diplomacy.sync_commands(now, scores, saved)
    assert 'data modify storage realms:factions ids.f4 set value "p-sam"' in commands   # not 3, nor 1 or 2
    assert 'data modify storage realms:factions names.f1 set value {text:"Blue Herons Two"}' in commands
    assert "scoreboard players set SamFake st.faction 4" in commands
    assert "scoreboard players set TomFake st.leader 1" in commands
    assert "scoreboard players reset RiaFake st.leader" in commands
    assert "scoreboard players set SamFake st.leader 1" in commands
    assert not any("#x" in c for c in commands)   # a fake player's score is never touched


def test_numbers_run_out_with_a_warning_and_a_bad_name_is_left_out():
    taken = {"ids": {f"f{n}": f"p-{n:03}" for n in range(1, diplomacy.MAX_FACTIONS + 1)}}
    warned = []
    late = [diplomacy.Faction("p-zzz", "Late", ["Late_One", "not a name;say hi"])]
    assert diplomacy.sync_commands(late, {}, {"factions": taken}, warned.append) == []
    assert "no faction number left" in warned[0]
    warned.clear()
    commands = diplomacy.sync_commands(late, {}, {}, warned.append)
    assert "scoreboard players set Late_One st.faction 1" in commands
    assert not any("say" in c for c in commands) and "not a player name" in warned[0]


def test_numbers_and_names_read_the_saved_storage(tmp_path):
    world = tmp_path / "world"
    world.mkdir()
    assert diplomacy.saved_storage(world) == {} and diplomacy.numbers(world) == {}
    storage(world, {"factions": {"ids": {"f1": "p-blue", "f2": "p-red", "x": "odd"},
                                 "names": {"f2": {"text": "Red Monkeys"}}}, "standings": {"week": {"text": ""}}})
    assert diplomacy.numbers(world) == {"p-blue": 1, "p-red": 2}
    assert diplomacy.names(world) == {2: "Red Monkeys"}
    (world / "data" / "realms" / "command_storage.dat").write_bytes(nbt({"data": {"contents": "no"}}))
    with pytest.raises(ValueError, match="command_storage.dat: not as the server saves it"):
        diplomacy.saved_storage(world)


def test_the_hourly_board_run_writes_the_factions_first(tmp_path, capsys):
    world = make_world(tmp_path)
    server = rcon.Recorder()
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 0
    first_board = next(i for i, c in enumerate(server.sent) if c.startswith("data modify storage realms:standings"))
    synced = server.sent[:first_board]
    assert "scoreboard players set AlexFake st.faction 3" in synced   # p-blue 1, p-lone 2, p-red 3
    assert 'data modify storage realms:factions names.f2 set value {text:"LoneFake\'s faction"}' in synced
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
    assert server.sent[0].startswith("data modify storage realms:standings week")


def test_a_refused_sync_stops_the_board_run(tmp_path, capsys):
    world = make_world(tmp_path)
    server = rcon.Recorder({"scoreboard players set": "Unknown or incomplete command"})
    assert standings.board(world, tmp_path / "state", server, SUNDAY) == 1
    assert "could not update the in-game board" in capsys.readouterr().err
    assert not any(c.startswith("data modify storage realms:standings") for c in server.sent)


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
                           {"dp.pact": {"#1.3": 1, "#2.3": 0, "#4.5": 1}}, since=3)
    assert got["diplomacy_seq"] == 8
    assert got["diplomacy"] == [
        "**War and pacts this week**",
        "- Red Monkeys declared war on Blue Herons",
        "- Blue Herons and Lone\\_\\*Wolf\\* made a pact",   # offers stay in game; Discord markup is escaped
        "- Blue Herons broke its pact with Lone\\_\\*Wolf\\*",
        "- Faction 9 and Red Monkeys made peace, and a pact",   # a faction that is gone keeps its number
        "Pacts standing: Blue Herons and Red Monkeys.",
        "Every war ends with the week: a leader can declare again in game with `/trigger diplomacy`.",
    ]


def test_a_quiet_week_reports_nothing_and_a_new_world_starts_the_count_again():
    assert diplomacy.report({}, {}, since=0) == {"diplomacy": [], "diplomacy_seq": 0}
    assert diplomacy.report({"diplomacy": {"log": LOG}}, {}, since=8)["diplomacy"] == []
    # A new season's world numbers its log from 1 again: under last week's 8, all of it is new.
    fresh = diplomacy.report({"diplomacy": {"log": [{"n": 1, "kind": "war", "a": 1, "b": 2}]}}, {}, since=8)
    assert fresh["diplomacy"][1] == "- Faction 1 declared war on faction 2" and fresh["diplomacy_seq"] == 1
    many = [{"n": i, "kind": "war", "a": 1, "b": 2} for i in range(1, 30)]
    lines = diplomacy.report({"diplomacy": {"log": many}}, {}, since=0)["diplomacy"]
    assert len(lines) == 1 + diplomacy.REPORT_LIMIT + 2 and "- and 19 more" in lines


def test_close_posts_the_week_of_war_and_ends_the_wars_once(tmp_path, capsys):
    world = make_world(tmp_path, with_scores(("dp.pact", "#1.3", 1)))
    storage(world, {"diplomacy": {"log": LOG}, "factions": {"names": NAMES}})
    state = tmp_path / "state"
    (state / "weeks").mkdir(parents=True)
    (state / "week.json").write_text(json.dumps(BASELINE))
    (state / "weeks" / "2026-10-25.json").write_text(json.dumps(
        {"start": None, "end": "2026-10-25T19:00:00-07:00", "rows": [], "announced": True, "posted": True,
         "diplomacy_seq": 3}))
    server, discord = rcon.Recorder(), FakeDiscord()
    assert standings.close(world, state, server, SUNDAY, WEBHOOK, discord) == 0
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["diplomacy_seq"] == 8 and closed["wars_ended"]
    assert server.sent.index("function realms:standings/announce") < server.sent.index(
        "function realms:diplomacy/week_over")
    content = discord.posts[0][2]["content"]
    assert "- Red Monkeys declared war on Blue Herons" in content and len(content) <= standings.DISCORD_LIMIT
    assert content.index("```\n**War and pacts") < content.index("Scored as")
    # a retry closes nothing and ends no war twice
    assert standings.close(world, state, server, SUNDAY + dt.timedelta(minutes=5), WEBHOOK, discord) == 0
    assert server.sent.count("function realms:diplomacy/week_over") == 1
    # the next week reports only what came after
    nxt = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert diplomacy.report({"diplomacy": {"log": LOG}}, {}, nxt["diplomacy_seq"])["diplomacy"] == []


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
    assert "function realms:diplomacy/week_over" not in server.sent


# ---------------------------------------------------------------- the data pack


def test_the_pack_has_no_problems_with_the_standings_pack():
    # with every other pack, as they ship (#launched rw.day is the wardrobe's)
    assert [p for p in datapacks.problems(datapacks.all_files()) if "diplomacy" in p] == []
    tags = standings.datapack_files()
    assert "realms:diplomacy/load" in tags["data/minecraft/tags/function/load.json"]
    assert "realms:diplomacy/tick" in tags["data/minecraft/tags/function/tick.json"]


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
    assert adv["rewards"] == {"function": f"realms:diplomacy/kill/f{n}"}
    reward = fn(f"kill/f{n}").splitlines()
    assert reward[1] == f"advancement revoke @s only realms:diplomacy/kill/f{n}"   # first, so the next kill fires
    assert reward[2] == f"function realms:diplomacy/kill {{b:{n}}}"


def test_a_war_kill_counts_only_at_war_outside_the_arena_after_the_launch():
    kill = fn("kill")
    for gate in ("execute unless score #launched rw.day matches 1 run return 0",
                 "execute if entity @s[tag=ev.arena] run return 0",
                 "execute unless score @s st.faction matches 1.. run return 0"):
        assert kill.index(gate) < kill.index("function realms:diplomacy/pair")
    war_kill = fn("war_kill").splitlines()
    assert war_kill[0] == "$execute unless score #$(lo).$(hi) dp.war matches 1 run return 0"
    assert war_kill[1] == "scoreboard players add @s st.warkills 1"


def test_pair_puts_the_smaller_number_first():
    pair = fn("pair")
    assert "scoreboard players operation #lo dp.tmp < #b dp.tmp" in pair
    assert "scoreboard players operation #hi dp.tmp > #b dp.tmp" in pair


def test_only_an_owner_acts_and_only_after_the_launch():
    use = fn("use")
    order = ["unless score #launched rw.day matches 1", "unless score @s st.faction matches 1..",
             "run return run function realms:diplomacy/menu", "unless score @s st.leader matches 1",
             "if score #a dp.tmp = #b dp.tmp", "unless function realms:diplomacy/known",
             "if function realms:diplomacy/cooling", "matches 1 run return run function realms:diplomacy/war"]
    at = [use.index(s) for s in order]
    assert at == sorted(at)
    assert "matches ..9 run return run function realms:diplomacy/menu" in use


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
    assert war.index("$execute if score #$(lo).$(hi) dp.pact matches 1 run return run") < war.index(
        "$scoreboard players set #$(lo).$(hi) dp.war 1")
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
        assert f'$function realms:diplomacy/log {{kind:"{kind}",a:$(a),b:$(b)}}' in body, name
    for name in ("war", "pact", "accept", "break"):
        assert "$execute store result score #f$(a) dp.last run time query gametime" in fn(name)
    # breaking a pact names the player who did it
    assert '{"selector":"@s"' in fn("break")
    assert f"matches 0..{diplomacy.COOLDOWN_SECONDS * 20 - 1} run return 1" in fn("cooling_of")


def test_the_week_ends_wars_and_offers_but_not_pacts():
    over = fn("week_over")
    assert "scoreboard players reset * dp.war" in over and "scoreboard players reset * dp.offer" in over
    assert "dp.pact" not in over.replace("dp.pacts", "")


def test_the_launch_clears_what_came_before_it_once():
    second = fn("second")
    assert ("execute if score #launched rw.day matches 1 unless score #launched dp.state matches 1 run function "
            "realms:diplomacy/launch") in second
    launch = fn("launch")
    for o in ("dp.war", "dp.pact", "dp.offer", "dp.pacts", "st.warkills"):
        assert f"scoreboard players reset * {o}" in launch
    assert launch.rstrip().endswith("scoreboard players set #launched dp.state 1")


def test_the_menu_lists_every_number_but_your_own():
    menu = fn("menu")
    assert menu.count("run function realms:diplomacy/row {b:") == diplomacy.MAX_FACTIONS
    assert ("execute if data storage realms:factions names.f7 unless score @s st.faction matches 7 run function "
            "realms:diplomacy/row {b:7}") in menu
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

