import datetime as dt
import json

import border
import boss
import pytest
from fake_world import FakeWorld
from test_border import ACT_ONE, ACT_TWO, LAUNCHED, SEASON_TWO, make_server

import datapacks
import firsts
import news
import rcon
import season_calendar

PACIFIC = season_calendar.PACIFIC
FILES = boss.datapack_files()
FN = "data/monkey/function/boss"


def body(name: str) -> str:
    return FILES[f"{FN}/{name}.mcfunction"]


@pytest.mark.parametrize("act", border.acts(2), ids=lambda a: f"act{a.number}")
@pytest.mark.parametrize("centre", [(0.0, 0.0), (137.5, -2210.5)])
def test_the_spot_is_inside_the_new_edge_and_past_the_old_border(act, centre):
    before = [a.size for a in border.acts(2) if a.number < act.number] or [2500]
    x, z = boss.spot(2, act.number, *centre, act.size)
    reach = max(abs(x - centre[0]), abs(z - centre[1]))
    assert before[-1] / 2 < reach <= act.size / 2 - boss.INSET + 1
    assert boss.spot(2, act.number, *centre, act.size) == (x, z)   # seeded: a retry picks the same spot


def test_health_is_scaled_and_capped():
    assert boss.BASE_HEALTH <= boss.MIN_HEALTH < boss.MAX_HEALTH <= 1024
    summon = body("summon")
    assert f"scoreboard players set #k bs {boss.PER_PLAYER}" in summon
    assert f"matches ..{boss.MIN_HEALTH - 1} run scoreboard players set #hp bs {boss.MIN_HEALTH}" in summon
    assert f"matches {boss.MAX_HEALTH + 1}.. run scoreboard players set #hp bs {boss.MAX_HEALTH}" in summon
    assert "drop_chances:{mainhand:0.0f" in summon and "PersistenceRequired:1b" in summon


def test_off_by_default_and_never_in_season_one():
    assert "scoreboard players add #on bs 0" in body("load")      # a new world: off, and a reload keeps staff's choice
    act = body("act").splitlines()
    assert act.index("execute unless score #on bs matches 1 run return 10") < act.index("return 1")
    assert "execute unless score #season rw.day matches 2.. run return 11" in act
    assert "execute unless score #launched rw.day matches 1 run return 12" in act
    assert "execute if score #season_locked ev.state matches 1 run return 13" in act
    assert "matches 2.. run return run tellraw" in body("on")    # the switch refuses a Season I world


def test_each_act_raises_one_boss():
    act = body("act")
    assert "$execute if score #act bs matches $(act).. run return 14" in act
    assert "execute if score #state bs matches 1.. run return 15" in act
    assert act.index("return 14") < act.index("$scoreboard players set #act bs $(act)")
    assert 'acts.a$(act) set value {state:"waiting",x:$(x),z:$(z),hp:0}' in act   # a record from the start
    off = body("off")   # turned off while it waits: it never rose, so it didn't "leave"
    assert 'matches 1 run function monkey:boss/record {state:"off"}' in off
    assert 'matches 2 run function monkey:boss/record {state:"left"}' in off
    assert body("vanish").splitlines()[2] == "execute at @s run tp @s ~ -200 ~"   # out of the world where it stands


def test_the_kill_advancement_and_the_first_read_the_boss_score():
    adv = json.loads(FILES["data/monkey/advancement/boss/slain.json"])
    assert adv["criteria"]["kill"]["conditions"]["entity"]["scores"] == {boss.ID: {"min": 1}}
    m = firsts.milestone("boss")
    assert m["season"] == 2 and m["conditions"]["entity"]["scores"] == {boss.ID: {"min": 1}}
    terms = firsts.advancement(m)["criteria"]["boss"]["conditions"]["player"]["terms"]
    assert datapacks.score_check("#season", "rw.day", least=2) in terms
    show = firsts.show_function(m).splitlines()
    assert show[1] == "execute unless score #season rw.day matches 2.. run return 0"   # hidden in Season I's menu
    assert "execute unless score #season rw.day matches 2.. run return 0" in firsts.got_function(m)


def test_the_packs_have_no_problems():
    files = datapacks.all_files()
    assert "monkey-boss/data/monkey/function/boss/act.mcfunction" in files
    assert "monkey-finale/data/monkey/function/finale/start.mcfunction" in files
    assert datapacks.problems(files) == []


def test_the_act_raises_the_boss_after_the_record(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, SEASON_TWO, LAUNCHED)
    sent = border.commands(world, ACT_ONE)
    assert sent[-2] == "scoreboard players set #border_act ev.state 1"
    x, z = boss.spot(2, 1, *border_centre(world), 4000)
    assert sent[-1] == f"function monkey:boss/act {{act:1,x:{x},z:{z},delay:{boss.RISE_SECONDS}}}"
    log = []
    server = rcon.Recorder({"function monkey:boss/act": "Function monkey:boss/act returned 10"})
    assert border.send(server, world, ACT_ONE, log.append) == 0
    assert log[-1].endswith(": the boss is off (function monkey:boss/on)")


def test_no_boss_in_season_one(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, ("rw.day", "#season", 1), LAUNCHED)
    for when in (ACT_ONE, ACT_TWO, dt.datetime(2026, 11, 21, 18, 1, tzinfo=PACIFIC)):
        assert not any("boss" in c for c in border.commands(world, when))


def border_centre(world):
    import saved_world
    b = saved_world.border(world)
    return b.center_x, b.center_z


def test_outcomes_news_and_status(tmp_path):
    world = FakeWorld(tmp_path / "world").scores(SEASON_TWO, LAUNCHED).storage("monkey", {
        "boss": {"acts": {"a1": {"state": "slain", "x": 10, "z": 2000, "hp": 500, "name": "Steve", "faction": 3,
                                 "week": 2},
                          "a2": {"state": "risen", "x": -2950, "z": 4, "hp": 300, "week": 8}}},
        "factions": {"names": {"f3": {"text": "Red Monkeys"}}}}).path
    found = boss.outcomes(world)
    assert [(o.act, o.state, o.player, o.faction, o.week) for o in found] == [
        (1, "slain", "Steve", 3, 2), (2, "risen", "", 0, 8)]
    assert boss.describe(found[0], {3: "Red Monkeys"}) == \
        "Act 1: The Edgewalker was slain by Steve (Red Monkeys), near 10, 2000."
    items = news.event_items(world, news.read_saved(world))
    assert [(i.key, i.text) for i in items] == [
        ("event:boss1:end", "Steve of Red Monkeys slew The Edgewalker."),
        ("event:boss2:rose", "The Edgewalker has risen near -2950, 4, past the old border. The first to slay it "
                             "takes a Server First.")]


def test_no_news_in_a_world_without_a_boss(tmp_path):
    world = FakeWorld(tmp_path / "world").scores(("rw.day", "#season", 1), LAUNCHED).path
    assert news.event_items(world, news.read_saved(world)) == []


def test_the_fight_is_a_staff_event_away_from_spawn():
    # Rule 41: at staff events anyone can fight anyone in the event area; say so where players read it.
    for name in ("act", "risen"):
        assert "A staff event" in body(name) and f"within {boss.EVENT_RADIUS} blocks of it" in body(name)
    # It rises 48 blocks inside an act's new edge: far past spawn's no-PvP zone (rules 22 and 26).
    for act in border.acts(2):
        x, z = boss.spot(2, act.number, 0.0, 0.0, act.size)
        assert max(abs(x), abs(z)) - boss.EVENT_RADIUS > 64
