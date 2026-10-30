import re

import pytest
from test_challenges import ALLOWED_STATS

import challenges
import goal
import recap
import standings
import wardrobe
from repo import REPO

FN = "data/monkey/function/goal"


def fn(name: str) -> str:
    return wardrobe.datapack_files()[f"{FN}/{name}.mcfunction"]


def body(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


# ---------------------------------------------------------------- the pool


def test_the_pool_is_well_formed():
    ids = [g["id"] for g in goal.POOL]
    assert len(ids) == len(set(ids)) and len(ids) >= 4
    for g in goal.POOL:
        assert re.fullmatch(r"[a-z]+", g["id"]), g["id"]
        assert 0 < len(g["name"]) <= goal.NAME_MAX, g["name"]
        assert g["target"] > 0 and g["about"]
        assert ("mine" in g) != ("stat" in g), g["id"]
        if "stat" in g:
            # Real play only: never distance or time online (a water stream or an AFK pool would farm them).
            # Mob kills are fine for a goal: they never count players, and nothing is given.
            assert g["stat"] in ALLOWED_STATS | {"mob_kills"}, g["stat"]


def test_mining_counts_mined_minus_placed():
    logs = goal.POOL[0]
    assert logs["id"] == "logs" and logs["mine"] == challenges.LOGS   # the launch weekend's: everyone chops
    signs = {crit.split(":", 1)[0]: sign for _, crit, sign in goal.counters(logs)}
    assert signs == {"minecraft.mined": 1, "minecraft.used": -1}
    count = fn("count/logs")
    for o, _, sign in goal.counters(logs):
        assert (f"scoreboard players operation #total rg {'+=' if sign > 0 else '-='} "
                f"@a[gamemode=!creative,gamemode=!spectator] {o}") in count
        assert f"scoreboard players reset @a {o}" in count


def test_every_counter_is_created_and_cleared_at_the_week():
    load, restart = fn("load"), fn("restart")
    for o, crit in goal.objectives():
        assert f"scoreboard objectives add {o} {crit}" in load
        if crit != "dummy":
            assert f"scoreboard players reset * {o}" in restart
    assert "scoreboard players set #total rg 0" in restart and "scoreboard players set #said rg 0" in restart


# ---------------------------------------------------------------- the week


def run_pick(week: int, held: int = -2) -> int:
    """Runs goal/pick the way the server would; returns the POOL index set (via goal/set/<id>)."""
    scores = {"#week rc.week": week, "#week rg": held}
    chosen = None
    for line in body(fn("pick")):
        if line == "execute if score #week rg = #week rc.week run return 0":
            if scores["#week rg"] == scores["#week rc.week"]:
                return chosen
        elif m := re.fullmatch(r"scoreboard players operation (#\w+ r\w+(?:\.\w+)?) = (#\w+ r\w+(?:\.\w+)?)", line):
            scores[m[1]] = scores[m[2]]
        elif m := re.fullmatch(r"execute if score (#\w+ rg) matches \.\.-1 run scoreboard players set (#\w+ rg) 0",
                               line):
            if scores[m[1]] <= -1:
                scores[m[2]] = 0
        elif m := re.fullmatch(r"scoreboard players set (#\w+ rg) (\d+)", line):
            scores[m[1]] = int(m[2])
        elif m := re.fullmatch(r"scoreboard players operation (#\w+ rg) %= (#\w+ rg)", line):
            scores[m[1]] %= scores[m[2]]
        elif m := re.fullmatch(r"execute if score #idx rg matches (\d+) run function monkey:goal/set/(\w+)", line):
            if scores["#idx rg"] == int(m[1]):
                assert chosen is None
                chosen = int(m[1])
                assert goal.POOL[chosen]["id"] == m[2]
        else:
            raise AssertionError(line)
    return chosen


@pytest.mark.parametrize("week", [-1, 0, 1, 2, 6, 7, 8, 13, 40])
def test_the_server_picks_what_the_schedule_says(week):
    assert goal.POOL[run_pick(week)] is goal.pick(week)
    # The same week again (a restart) keeps what it has: a target staff changed stays.
    assert run_pick(week, held=week) is None


def test_the_goal_follows_the_challenges_week():
    files = wardrobe.datapack_files()
    pick = body(files["data/monkey/function/challenges/pick.mcfunction"])
    restart = body(files["data/monkey/function/challenges/restart.mcfunction"])
    assert pick[-1] == "function monkey:goal/pick"          # after the week is known
    assert "function monkey:goal/restart" in restart        # Monday's rollover and the launch
    load = body(files["data/monkey/function/wardrobe/load.mcfunction"])
    assert load.index("function monkey:goal/load") < load.index("function monkey:challenges/load")
    for g in goal.POOL:
        set_ = fn(f"set/{g['id']}")
        assert f"scoreboard players set #target rg {g['target']}" in set_
        assert f'data modify storage monkey:goal name set value "{g["name"]}"' in set_


def test_schedule_names_each_weeks_goal():
    out = goal.schedule(0, len(goal.POOL) + 1).splitlines()
    assert out[0].startswith("week 0") and goal.POOL[0]["name"] in out[0]
    assert goal.POOL[0]["name"] in out[-1]   # it comes round again


# ---------------------------------------------------------------- counting and the milestones


def test_nothing_counts_before_the_launch_or_while_off():
    lines = body(fn("second"))
    assert lines[0] == "execute unless score #on rg matches 1 run return 0"
    assert lines[1] == f"execute unless score {challenges.LAUNCHED} matches 1 run return 0"
    second = body(wardrobe.datapack_files()["data/monkey/function/wardrobe/second.mcfunction"])
    assert "function monkey:goal/second" in second
    # Every CHECK_SECONDS, not every tick: the online players' counts are added and cleared.
    assert f"execute if score #sec rg matches ..{goal.CHECK_SECONDS - 1} run return 0" in lines


def milestones(pct: int, said: int) -> list[str]:
    """Which of goal/reached and goal/half one check runs, in order, for this percentage and #said."""
    ran = []
    for line in body(fn("second")):
        m = re.fullmatch(r"execute if score #pct rg matches (\d+)\.\. unless score #said rg matches (\d+)\.\. "
                         r"run function monkey:goal/(\w+)", line)
        if m and pct >= int(m[1]) and not said >= int(m[2]):
            ran.append(m[3])
            said = 100 if m[3] == "reached" else goal.HALF
    return ran


def test_each_milestone_is_said_once():
    assert milestones(10, 0) == []
    assert milestones(50, 0) == ["half"]
    assert milestones(70, 50) == []
    assert milestones(100, 50) == ["reached"]
    assert milestones(100, 0) == ["reached"]   # all at once: the celebration, not half way after it
    assert milestones(140, 100) == []


def test_the_celebration_is_fireworks_and_a_title_never_an_item():
    reached = fn("reached")
    assert "title @a title " in reached and "tellraw @a " in reached
    assert reached.count("summon minecraft:firework_rocket") == 3
    assert f"@e[type=minecraft:text_display,tag={standings.BOARD_TAG}]" in reached
    assert goal.BOARD == standings.BOARD_TAG
    for text in (fn(name) for name in ("reached", "half", "second", "line")):
        assert "give " not in text and "loot " not in text


def test_the_line_shows_under_the_challenges():
    files = wardrobe.datapack_files()
    assert "function monkey:goal/line" in files["data/monkey/function/wardrobe/menu_challenges.mcfunction"]
    assert "function monkey:goal/line" in files["data/monkey/function/challenges/greet.mcfunction"]
    line = body(fn("line"))
    assert line[0] == "execute unless score #on rg matches 1 run return 0"
    assert sum(x.startswith("tellraw @s ") for x in line) == 1


def test_the_switch_and_target():
    load = fn("load")
    assert f"execute unless score #on rg matches 0.. run scoreboard players set #on rg {goal.GOAL_ON}" in load
    assert "scoreboard players set #on rg 1" in fn("on") and "scoreboard players set #on rg 0" in fn("off")
    assert "$scoreboard players set #target rg $(n)" in fn("target")
    seasons = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8")
    assert "function monkey:goal/off" in seasons and "function monkey:goal/on" in seasons


# ---------------------------------------------------------------- the Sunday recap


def held(**scores) -> dict:
    return {"rg": {f"#{k}": v for k, v in scores.items()}}


def test_the_recap_line():
    fish = next(i for i, g in enumerate(goal.POOL) if g["id"] == "fish")
    assert goal.recap_line({}, 3) == []                                            # no goal in this world
    assert goal.recap_line(held(on=0, week=3, idx=fish, total=50), 3) == []        # off
    assert goal.recap_line(held(on=1, week=3, idx=fish, total=0, target=400), 3) == []   # nothing counted
    assert goal.recap_line(held(on=1, week=4, idx=fish, total=10, target=400), 3) is None   # another week's
    part = goal.recap_line(held(on=1, week=3, idx=fish, total=100, target=400, said=0), 3)
    assert part == ["**Server goal:** Catch fish: 100 of 400 so far (25%), until Monday 12 AM Pacific."]
    done = goal.recap_line(held(on=1, week=3, idx=fish, total=1234, target=400, said=100), 3)
    assert done == ["**Server goal:** Catch fish: reached, 1,234 of 400. Fireworks at spawn."]
    # The launch weekend: the week score was -1 before the first sync.
    assert goal.recap_line(held(on=1, week=-1, idx=0, total=5, target=4000), 0)


def test_the_recap_has_a_goal_section():
    assert recap.server_goal in recap.SECTIONS
    assert recap.SECTIONS.index(recap.server_goal) == recap.SECTIONS.index(recap.challenges) + 1
