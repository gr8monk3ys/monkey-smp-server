import re

import pytest

import datapacks
import lore
import npcs
import season_calendar
from repo import REPO

FILES = lore.datapack_files()
FN = "data/monkey/function/lore"


def test_the_beats_match_the_calendar_weeks():
    """One page a week from week 1 to the finale, and each page about an event falls in that event's week."""
    assert 7 <= len(lore.BEATS) <= 12
    assert tuple(range(1, npcs.LAST_WEEK)) == lore.WEEKS   # week 12 is the locked off-season: no page
    assert "finale" in npcs.EVENTS[lore.LAST]
    for week, beat in lore.BEATS.items():
        assert season_calendar.week_start(week) < season_calendar.SEASON_TWO
        if beat.tie:
            assert beat.tie in npcs.EVENTS[week], (week, beat.tie, npcs.EVENTS[week])
    # Every week the calendar changes the world has the page about it.
    for tie in ("border", "End", "Netherite", "finale"):
        weeks = {w for w in lore.WEEKS if tie in npcs.EVENTS[w]}
        assert weeks, tie
        assert weeks == {w for w, b in lore.BEATS.items() if b.tie == tie}, tie


def test_the_book_fits_a_book():
    for week, beat in lore.BEATS.items():
        assert 0 < len(beat.title) <= 32, week
        assert 1 <= len(beat.pages) <= 4, week
        assert all(0 < len(p) <= lore.PAGE_CHARACTERS for p in beat.pages), week
        assert beat.cry and beat.where, week
        assert all(c.isascii() for c in beat.title + beat.cry + beat.where + "".join(beat.pages)), week


def test_it_ships_off_and_waits_for_the_switch_and_the_launch():
    assert lore.LORE_ON == 0
    load = FILES[f"{FN}/load.mcfunction"]
    assert "execute unless score #on lr matches 0.. run scoreboard players set #on lr 0" in load
    second = FILES[f"{FN}/second.mcfunction"].splitlines()
    off = second.index("execute unless score #on lr matches 1 run return 0")
    launched = second.index("execute unless score #launched rw.day matches 1 run return 0")
    greet = next(i for i, line in enumerate(second) if "lore/greet" in line)
    caches = next(i for i, line in enumerate(second) if "lore/cache" in line)
    assert off < launched < greet and launched < caches
    assert len(second) <= 10   # once a second: keep it lean


def test_each_week_has_its_functions_and_a_page_shows_only_from_its_week():
    cache = FILES[f"{FN}/cache.mcfunction"]
    for w in lore.WEEKS:
        for kind in ("hide", "near", "find", "book"):
            assert f"{FN}/{kind}/{w}.mcfunction" in FILES
        assert f"execute if entity @s[tag=lore.w{w}] if score #week rc.week matches {w}.. run function " \
               f"monkey:lore/near/{w}" in cache
        find = FILES[f"{FN}/find/{w}.mcfunction"].splitlines()
        assert find[1] == f"execute if score @s lr.w{w} matches 1 run return 0"   # once each
        assert f"execute if score @s lr.found matches {lore.PAGES}.. run function monkey:lore/complete" in find
        assert f"tag=lore.w{w}" in FILES[f"{FN}/hide/{w}.mcfunction"]
        assert f"distance=..{lore.REACH}" in FILES[f"{FN}/near/{w}.mcfunction"]


def test_the_book_item():
    item = lore.book(3)
    assert item.startswith('minecraft:written_book[minecraft:written_book_content={title:"The Far Gate",author:')
    assert "Page 3 of 11" in item
    assert re.fullmatch(r"give @s minecraft:written_book\[.*\]", FILES[f"{FN}/book/3.mcfunction"].splitlines()[1])


def test_the_title_is_a_carried_team_and_never_replaces_another():
    team, _color, prefix = lore.TITLE
    assert team.startswith("title_")   # tools/season.py carries title_* teams
    complete = FILES[f"{FN}/complete.mcfunction"].splitlines()
    keep = next(i for i, line in enumerate(complete) if line.startswith("execute unless entity @s[team=]"))
    assert complete.index(f"team join {team} @s") > keep
    assert prefix.strip() == "[Knotkeeper]"


def test_the_crier_line_names_the_page_and_the_trigger():
    greet = FILES[f"{FN}/greet.mcfunction"]
    assert greet.count("tellraw @s") == len(lore.WEEKS)
    assert "[Town Crier] " in greet and "/trigger lore" in greet


def test_the_pack_is_generated_and_clean():
    assert "lore" in datapacks.GENERATORS
    pack = lore.packs(REPO)[REPO.monkey / "datapacks" / lore.DATAPACK]
    # read with every other pack: they ship and load together (rc.week, st.faction and rw.day are theirs)
    assert [p for p in datapacks.problems(datapacks.all_files()) if p.startswith("monkey-lore/")] == []
    assert '"monkey:lore/load"' in pack["data/minecraft/tags/function/load.json"]


@pytest.mark.parametrize("argv", [["plan"]])
def test_plan(capsys, argv):
    assert lore.main(argv) == 0
    out = capsys.readouterr().out
    assert out.count("function monkey:lore/hide/") == len(lore.WEEKS)
