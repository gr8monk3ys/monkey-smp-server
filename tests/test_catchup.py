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
    grant = fn("grant")
    assert grant.splitlines()[1] == "execute if score @s ck.kit matches 1 run return 0"
    assert grant.count("give @s ") == len(catchup.KIT)


def test_the_bubble_is_grace_held_open_for_hours_of_play():
    assert f"scoreboard players set @s ck.bubble {catchup.BUBBLE_HOURS * 3600}" in fn("grant")
    hold = fn("hold")
    assert "execute unless score @s monkey.grace >= #keep ck run scoreboard players operation @s monkey.grace " \
           "= #keep ck" in hold
    # it counts down only outside the arena, and shows on the action bar
    assert hold.index("@s[tag=ev.arena] run return") < hold.index("scoreboard players remove @s ck.bubble 1")
    assert "title @s actionbar" in hold
    second = fn("second", "rules")
    assert second.index("catchup/second") < second.index("run function monkey:rules/grace_end")
    assert "execute if entity @a[scores={ck.bubble=1..},limit=1] run function monkey:catchup/second" in second
    # hurting a player (rule 26's grace_attack) or /trigger end_grace ends it with the grace
    assert "scoreboard players reset @s ck.bubble" in fn("grace_end", "rules")
    assert "function monkey:catchup/load" in fn("load", "rules")
