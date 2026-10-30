import datetime as dt

from fake_world import FakeWorld

import datapacks
import monuments
import recap
import season
import season_calendar
import standings

FILES = monuments.datapack_files()
FN = "data/monkey/function/monuments"
WINNER = {"n": 1, "season": 1, "week": 3, "month": "November 2026", "theme": "The Gate", "f": 2,
          "faction": {"text": "Red Monkeys"}, "x": 120, "y": 64, "z": -300, "dim": "minecraft:overworld"}


def test_every_month_of_the_season_has_a_theme():
    keys = list(monuments.THEMES)
    assert keys == sorted(keys)
    first = season_calendar.SEASON.launch_day
    finale = season_calendar.saturday(11)
    month, months = (first.year, first.month), set()
    while month <= (finale.year, finale.month):
        months.add(f"{month[0]}-{month[1]:02}")
        month = (month[0] + month[1] // 12, month[1] % 12 + 1)
    assert months <= set(keys)
    for key, (name, theme, about) in monuments.THEMES.items():
        # the theme reaches chat lines through a macro, inside JSON strings
        assert not set('"\\$') & set(name + theme + about), key
        assert f"{FN}/open/{key}.mcfunction" in FILES


def test_it_ships_off_and_only_the_switch_lets_players_enter():
    assert monuments.MONUMENTS_ON == 0
    assert "execute unless score #on mn matches 0.. run scoreboard players set #on mn 0" in \
        FILES[f"{FN}/load.mcfunction"]
    second = FILES[f"{FN}/second.mcfunction"].splitlines()
    assert second.index("execute unless score #on mn matches 1 run return 0") < \
        second.index("scoreboard players enable @a monument")
    use = FILES[f"{FN}/use.mcfunction"]
    assert "execute if score #use mn matches 1 if score #open mn matches 1 run return run function " \
           "monkey:monuments/submit" in use


def test_an_entry_is_the_faction_and_the_spot():
    submit = FILES[f"{FN}/submit.mcfunction"]
    assert "execute unless score @s st.faction matches 1.. run return run tellraw" in submit
    for axis in "xyz":
        assert f"execute store result storage monkey:monuments new.{axis} int 1 run data get entity @s Pos[" in submit
    save = FILES[f"{FN}/save.mcfunction"]
    assert "$data modify storage monkey:monuments entries.f$(f).faction set from storage monkey:factions names.f$(f)" \
        in save
    # one entry a faction: entering again moves it, and only the first is announced and listed
    assert "$execute if score #had mn matches 0 run data modify storage monkey:monuments order append value {f:$(f)}" \
        in save


def test_opening_starts_empty_and_winning_keeps_it_in_the_hall():
    opened = FILES[f"{FN}/open/2026-11.mcfunction"]
    assert 'contest set value {key:"2026-11",month:"November 2026",theme:"The Gate"' in opened
    assert "data remove storage monkey:monuments entries" in opened
    assert "scoreboard players set #open mn 1" in opened
    win = FILES[f"{FN}/win.mcfunction"].splitlines()
    assert win[1].startswith("execute if data storage monkey:monuments contest{won:1b} run return")
    for line in ("data modify storage monkey:monuments hall append from storage monkey:monuments won",
                 "execute store result storage monkey:monuments won.season int 1 run scoreboard players get "
                 "#season rw.day",
                 "execute store result storage monkey:monuments won.week int 1 run scoreboard players get "
                 "#week rc.week",
                 "scoreboard players set #open mn 0", "function monkey:monuments/announce with storage "
                 "monkey:monuments won"):
        assert line in win, line
    assert "title @a title" in FILES[f"{FN}/announce.mcfunction"]
    assert "$execute in $(dim) run tp @s $(x) $(y) $(z)" in FILES[f"{FN}/go.mcfunction"]


def test_the_pack_is_clean():
    # read with every other pack: they ship and load together (rc.week, st.faction and rw.day are theirs)
    assert [p for p in datapacks.problems(datapacks.all_files()) if p.startswith("monkey-lore/")] == []


def world_with_hall(path, *rows):
    fake = FakeWorld(path).scores(("rw.day", "#season", 1))
    fake.storage("monkey", {"monuments": {"hall": list(rows),
                                          "contest": {"month": "November 2026", "theme": "The Gate"},
                                          "entries": {"f2": WINNER, "f10": {**WINNER, "f": 10, "faction":
                                                                             {"text": "Blue Herons"}}}}})
    return fake.path


def test_season_carry_puts_the_hall_back(tmp_path):
    old = world_with_hall(tmp_path / "old" / "world", WINNER)
    new = tmp_path / "new" / "world"
    assert season.main(["carry", str(old), "--into", str(new), "--season", "2"]) == 0
    run = (new / "datapacks/monkey-carry/data/monkey/function/carry/run.mcfunction").read_text().splitlines()
    hall = next(i for i, line in enumerate(run) if line.startswith("data modify storage monkey:monuments hall set"))
    assert run[hall] == ('data modify storage monkey:monuments hall set value [{n:1,season:1,week:3,month:'
                         '"November 2026",theme:"The Gate",f:2,faction:{text:"Red Monkeys"},x:120,y:64,z:-300,'
                         'dim:"minecraft:overworld"}]')
    assert run.index("execute if score #carried rw.day matches 1 run return 0") < hall < \
        run.index("scoreboard players set #carried rw.day 1")


def test_no_hall_carries_nothing(tmp_path):
    old = FakeWorld(tmp_path / "old").scores(("rw.day", "#season", 1)).path
    assert monuments.carry_lines(old) == []


def test_the_recap_names_the_week_a_monument_was_won(tmp_path):
    folder = world_with_hall(tmp_path / "world", WINNER)
    world = standings.World([], {}, {"rw.day": {"#season": 1}}, {})
    end = dt.datetime(2026, 11, 29, 19, 0, tzinfo=season_calendar.PACIFIC)   # closes week 3
    week = recap.Week([], world, {"start": dt.datetime(2026, 11, 23, tzinfo=season_calendar.PACIFIC).isoformat()},
                      None, end, folder)
    assert week.number == 3
    assert recap.monument(week) == ["**Monument of the Month:** Red Monkeys won November 2026, The Gate, at "
                                    "120 64 -300."]
    week.end = end + dt.timedelta(days=7)
    week.start = {"start": (end + dt.timedelta(days=1)).isoformat()}
    assert recap.monument(week) == []
    week.folder = None
    assert recap.monument(week) == []


def test_entries_and_hall_for_staff(tmp_path, capsys):
    folder = world_with_hall(tmp_path / "world", WINNER)
    assert monuments.main(["entries", str(folder)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Monument of the Month, November 2026: The Gate."
    assert out[1].startswith("**Red Monkeys** (faction 2): 120 64 -300 in overworld.")
    assert out[2].startswith("**Blue Herons** (faction 10)")   # by number, not as text
    assert monuments.main(["hall", str(folder)]) == 0
    assert capsys.readouterr().out.strip() == ("1. Season 1, November 2026, The Gate: Red Monkeys at 120 64 -300 "
                                               "(overworld)")
    assert monuments.main(["plan"]) == 0
    assert "function monkey:monuments/open/2026-11" in capsys.readouterr().out
