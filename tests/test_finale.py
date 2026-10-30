import datetime as dt

import border
import finale
from fake_world import FakeWorld
from test_border import LAUNCHED, SEASON_TWO, SPAWN, make_server

import diplomacy
import rcon
import recap
import season_calendar

PACIFIC = season_calendar.PACIFIC
FILES = finale.datapack_files()
FN = "data/monkey/function/finale"
FINALE = dt.datetime(2027, 4, 24, 18, 1, tzinfo=PACIFIC)     # Season II, week 11, a minute after its time
ACTS_DONE = ("ev.state", "#border_act", 2)
ON = ("fn", "#on", 1)


def body(name: str) -> str:
    return FILES[f"{FN}/{name}.mcfunction"]


def test_the_finale_is_season_twos_week_eleven():
    assert finale.finale_at(2) == dt.datetime(2027, 4, 24, 18, 0, tzinfo=PACIFIC)
    assert finale.MAX_FACTIONS == diplomacy.MAX_FACTIONS
    stages = [what for _, what in finale.stages(finale.finale_at(2))]
    assert stages[0].startswith("warning: the border closes in 10 minutes") and stages[-1].startswith("the close")
    assert finale.CLOSE_AT - finale.HOLD_AT == 3600     # presence counts over the last hour


def test_never_below_the_safe_minimum_and_never_grown():
    assert finale.FINAL_SIZE >= finale.MIN_SIZE >= 2 * finale.RADIUS
    shrink = body("shrink")
    assert f"if score #size fn matches {finale.FINAL_SIZE + 1}.. in minecraft:overworld run worldborder set " \
           f"{finale.FINAL_SIZE} {finale.SHRINK_SECONDS * 20}" in shrink
    # slower than walking (4.3 blocks a second) at the edge, from Season II's widest border
    assert (6000 - finale.FINAL_SIZE) / 2 / finale.SHRINK_SECONDS < 1.5


def test_warnings_at_ten_minutes_one_minute_and_now():
    start, tick, shrink = body("start"), body("tick"), body("shrink")
    assert "in 10 minutes the border starts closing" in start and finale.SHRINK_AT == 600
    assert f"matches {finale.SHRINK_AT - 60} run tellraw @a" in tick and "closing in 1 minute" in tick
    assert f"matches {finale.SHRINK_AT} run function monkey:finale/shrink" in tick
    assert "the border is closing now" in shrink
    assert f"matches {finale.CLOSE_AT - 600} run tellraw" in tick and f"matches {finale.CLOSE_AT - 60} run tellraw" \
        in tick


def test_nobody_is_stranded():
    second, edge = body("second"), body("edge_at")
    assert "run scoreboard players add #edge fn 1" in second and "matches 2.." in second
    assert "as @a[distance=0..,gamemode=!spectator,gamemode=!creative] unless entity" in edge   # Overworld only
    assert "run title @s actionbar" in edge and "run function monkey:finale/inside" in edge
    assert "spreadplayers $(x) $(z) 0 $(r) false @s" in body("inside")


def test_off_by_default_and_never_in_season_one():
    assert "scoreboard players add #on fn 0" in body("load")
    start = body("start").splitlines()
    for guard in ("execute unless score #on fn matches 1 run return 10",
                  "execute unless score #season rw.day matches 2.. run return 11",
                  "execute unless score #launched rw.day matches 1 run return 12",
                  "execute if score #season_locked ev.state matches 1 run return 13",
                  "execute if score #started fn matches 1 run return 14"):
        assert start.index(guard) < start.index("scoreboard players set #started fn 1")
    assert "matches 2.. run return run tellraw" in body("on")


def test_presence_counts_faction_members_at_the_monument_in_the_last_hour():
    tick, sample = body("tick"), body("sample")
    assert "execute if score #phase fn matches 3 run function monkey:finale/sample" in tick
    assert "gamemode=survival" in sample and "scores={st.faction=1..}" in sample and "tag=!ev.arena" not in "" \
        and "dx=$(d)" in sample
    assert body("add") == "$scoreboard players add #f$(n) fn 1\n"
    pick = body("pick_one")
    assert "= #best fn run return run scoreboard players set #tie fn 1" in pick
    assert "close" in tick and "#tie fn matches 1 run scoreboard players set #win fn 0" in body("close")


def test_the_timer_starts_it_once_with_the_switch_on(tmp_path):
    world = make_server(tmp_path, 6000, 750, SEASON_TWO, LAUNCHED, ACTS_DONE, ON)
    assert border.commands(world, FINALE)[0] == finale.start_command(*SPAWN)
    assert not any("finale" in c for c in border.commands(world, FINALE - dt.timedelta(minutes=2)))
    log = []
    server = rcon.Recorder({"function monkey:finale/start": "Function monkey:finale/start returned 1"})
    assert border.send(server, world, FINALE, log.append) == 0
    assert log[-1].endswith("the finale has started: the border closes in 10 minutes")
    started = make_server(tmp_path / "s", 6000, 750, SEASON_TWO, LAUNCHED, ACTS_DONE, ON, ("fn", "#started", 1))
    assert not any("finale" in c for c in border.commands(started, FINALE))
    off = make_server(tmp_path / "o", 6000, 750, SEASON_TWO, LAUNCHED, ACTS_DONE)
    assert not any("finale" in c for c in border.commands(off, FINALE))


def test_no_finale_in_season_one(tmp_path):
    world = make_server(tmp_path, 2500, 312.5, ("rw.day", "#season", 1), LAUNCHED, ON)
    for when in (FINALE, dt.datetime(2027, 1, 23, 18, 1, tzinfo=PACIFIC)):
        assert not any("finale" in c for c in border.commands(world, when))


def result_world(tmp_path, result, *scores):
    return FakeWorld(tmp_path / "world").scores(SEASON_TWO, LAUNCHED, *scores).storage("monkey", {
        "finale": {"result": result},
        "factions": {"names": {"f3": {"text": "Red Monkeys"}, "f5": {"text": "Blue Jays"}}}}).path


def test_the_result_roster_and_staff_commands(tmp_path, capsys):
    world = result_world(tmp_path, {"faction": 3, "points": 4200, "tie": 0, "week": 11},
                         ("fn", "#f3", 4200), ("fn", "#f5", 900), ("st.faction", "Steve", 3),
                         ("st.faction", "alex", 3), ("st.faction", "Bob", 5))
    got = finale.result(world)
    assert (got.faction, got.points, got.tie, got.week, got.points_by) == (3, 4200, False, 11, {3: 4200, 5: 900})
    assert finale.roster(world, 3) == ["alex", "Steve"]
    assert finale.main(["result", str(world)]) == 0
    out = capsys.readouterr().out
    assert "Red Monkeys held the monument with 4200 points." in out
    assert "  scoreboard players set Steve rw.champion 1" in out and "  team join champion_s2 alex" in out


def test_a_tie_names_nobody(tmp_path, capsys):
    world = result_world(tmp_path, {"faction": 0, "points": 50, "tie": 1, "week": 11}, ("fn", "#f3", 50),
                         ("fn", "#f5", 50))
    assert finale.result(world).tie
    finale.main(["result", str(world)])
    assert "A tie on 50 points" in capsys.readouterr().out


def test_the_recap_names_the_winner_in_its_week(tmp_path, monkeypatch):
    monkeypatch.setattr(recap.Week, "number", property(lambda self: 11))
    world = result_world(tmp_path, {"faction": 3, "points": 4200, "tie": 0, "week": 11}, ("fn", "#f3", 4200))

    class World:
        scores = {"rw.day": {"#season": 2}, "fn": {"#f3": 4200}}
    week = recap.Week([], World(), {"start": "2027-04-19T00:00:00-07:00"}, None,
                      dt.datetime(2027, 4, 25, 19, 0, tzinfo=PACIFIC), folder=world)
    assert recap.spectacles(week) == ["**The finale:** Red Monkeys held the monument and won, with 4200 points."]
    monkeypatch.setattr(recap.Week, "number", property(lambda self: 10))
    assert recap.spectacles(week) == []
    week.world.scores = {"rw.day": {"#season": 1}}
    assert recap.spectacles(week) == []


def test_the_monument_and_its_event_area_stay_clear_of_spawn():
    # Rules 22 and 26: spawn is sacred and a no-PvP zone (the server claim over its 7 x 7 chunks, SPAWN_ZONE blocks
    # either way of the border's centre, which is spawn). Neither the hold zone nor the event area may touch it.
    assert finale.SPAWN_ZONE >= 3 * 16 + 15
    dx, dz = finale.MONUMENT_OFFSET
    gap = max(abs(dx), abs(dz))
    assert gap - finale.RADIUS > finale.SPAWN_ZONE and gap - finale.EVENT_RADIUS > finale.SPAWN_ZONE
    assert finale.EVENT_RADIUS >= finale.RADIUS
    assert finale.monument(-80.0, 416.0) == (-80 + dx, 416 + dz)
    want = f"function monkey:finale/start {{x:{-80 + dx},z:{416 + dz},cx:-80,cz:416}}"
    assert finale.start_command(-80.4, 416.0) == want


def test_the_border_moves_to_the_monument_slower_than_a_walk():
    assert max(map(abs, finale.MONUMENT_OFFSET)) <= finale.SHRINK_SECONDS * finale.STEER   # it gets there in time
    shrink_edge = (6000 - finale.FINAL_SIZE) / 2 / finale.SHRINK_SECONDS
    assert shrink_edge + finale.STEER < 4.3 / 1.9                                         # under half walking pace
    tick, steer = body("tick"), body("steer")
    assert "matches 2..3 run function monkey:finale/steer" in tick
    assert "if score #bx fn = #mx fn if score #bz fn = #mz fn run return 0" in steer
    assert body("center") == "$execute in minecraft:overworld run worldborder center $(bx) $(bz)\n"
    start = body("start")
    assert f"matches -{finale.SHRINK_SECONDS}..{finale.SHRINK_SECONDS} run return 15" in start
    assert "remove #a fn $(cx)" not in start and "#k fn $(cx)" in start   # remove refuses a negative (a real boot)
    assert "edge.x set from storage monkey:finale at.bx" in body("edge")    # moved inside around the centre, not
    assert "= #bx fn" in body("box")                                        # to the monument


def test_the_hold_is_announced_as_a_staff_event():
    for name in ("start", "hold"):
        assert "staff event" in body(name) and "rule 41" in body(name)
    assert "claim" not in "".join(FILES.values()).lower()     # never touches claims (rules 37, 39, 42)
