import re

import catchup

import rules

FILES = rules.rules_files()


def fn(name, folder="catchup"):
    return FILES[f"data/monkey/function/{folder}/{name}.mcfunction"]


def test_it_ships_off_and_only_late_first_joins_of_a_launched_season_get_it():
    assert catchup.CATCHUP_ON == 0
    assert "execute unless score #on ck matches 0.. run scoreboard players set #on ck 0" in fn("load")
    first = fn("first_join")
    assert "execute unless score #on ck matches 1 run return 0" in first
    assert "execute unless score #launched rw.day matches 1 run return 0" in first
    assert f"execute unless score #week rc.week matches {catchup.KIT_WEEK}.. run return 0" in first
    assert catchup.KIT_WEEK == 4   # after week 3
    # Only rule 26's first join calls it: anyone seen in test play or pre-season is never a first join again.
    rules_first = fn("first_join", "rules")
    assert rules_first.index("run return 0") < rules_first.index("function monkey:catchup/first_join")


def test_the_kit_is_modest_and_given_once():
    items = [item for item, _ in catchup.KIT]
    assert not [i for i in items if re.search("diamond|netherite|strength|totem|elytra|enchanted", i)]
    assert any("bed" in i for i in items) and any("pickaxe" in i for i in items) and any("beef" in i for i in items)
    give = fn("give")
    assert give.splitlines()[1] == "execute if score @s ck.kit matches 1 run return 0"
    assert give.count("give @s ") == len(catchup.KIT)
    assert "function monkey:catchup/give" in fn("first_join") and "function monkey:catchup/note" in fn("grant")


def test_no_bubble_and_the_welcome_tells_a_late_joiner_about_the_kit():
    assert not [p for p in FILES if p.startswith("data/monkey/function/catchup/") and
                any(n in p for n in ("hold", "second", "over"))]
    assert "grace" not in "".join(FILES.values()).lower()
    assert "if score @s ck.kit matches 1 run function monkey:catchup/note" in fn("welcome", "rules")
    assert "function monkey:catchup/load" in fn("load", "rules")
