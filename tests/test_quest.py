import json
import re

import challenges
import datapacks
import npcs
import outposts
import quest
import standings
import wardrobe
from repo import REPO

FN = "data/monkey/function/quest"


def pack() -> dict[str, str]:
    return wardrobe.datapack_files()


def fn(name: str) -> str:
    return pack()[f"{FN}/{name}.mcfunction"]


def body(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


# ---------------------------------------------------------------- the steps


def test_the_steps_are_well_formed():
    ids = [s["id"] for s in quest.STEPS]
    assert len(ids) == len(set(ids)) == 5
    for s in quest.STEPS:
        assert re.fullmatch(r"[a-z]+", s["id"]), s["id"]
        assert 0 < len(s["name"]) <= quest.NAME_MAX, s["name"]
        assert s["about"] and s["score"][1] >= 1


def test_every_step_reads_a_score_a_pack_creates():
    """Each step is counted from a score something on the server keeps: the pack that keeps it creates it."""
    files = datapacks.all_files()
    created = set(re.findall(r"scoreboard objectives add (\S+)", "\n".join(files.values())))
    for s in quest.STEPS:
        assert s["score"][0] in created, s["id"]
        assert quest.done_score(s) in created, s["id"]


def test_the_shared_steps_come_from_the_packs_that_keep_them():
    standings_load = standings.datapack_files()["data/monkey/function/standings/load.mcfunction"]
    assert f"scoreboard objectives add {standings.CLAIMED} dummy" in standings_load
    out = outposts.datapack_files()
    for i in range(1, outposts.COUNT + 1):
        near = out[f"data/monkey/function/outposts/o/{i}/near.mcfunction"]
        assert f"$scoreboard players set {outposts.zone(False)} {outposts.VISIT} 1" in near
    # Test play's visits go at the launch, with the rest of the outposts' scores.
    assert outposts.VISIT in out["data/monkey/function/outposts/launch.mcfunction"]
    assert {s["score"][0] for s in quest.STEPS} == {"rq.guide", "rq.home", "st.faction", standings.CLAIMED,
                                                     outposts.VISIT}


def test_the_guide_sets_its_step_and_opens_the_quest():
    guide = npcs.guide()
    assert npcs.GUIDE_STEP in guide["events"]["ON_INTERACTION"]
    assert guide["events"]["ON_INTERACTION"][-1] == {"Type": "OPEN_DEFAULT_DIALOG"}
    assert npcs.GUIDE_STEP["Cmd"] == "set:rq.guide:1"
    buttons = {b["Name"]: b for d in guide["dialogs"] for b in d["Buttons"]}
    assert npcs.trigger("quest") in buttons["Your first week"]["Actions"]


def test_the_bed_step_is_a_26x_advancement_open_only_while_the_step_is():
    adv = json.loads(pack()["data/monkey/advancement/quest/home.json"])
    crit = adv["criteria"]["bed"]
    assert crit["trigger"] == "minecraft:any_block_use"
    player = crit["conditions"]["player"]
    assert player["type"] == "minecraft:all_of" and '"condition":' not in json.dumps(adv)
    assert {"min": quest.ON, "max": quest.ON} in [t.get("scores", {}).get(quest.STATE) for t in player["terms"]]
    assert crit["conditions"]["location"]["predicate"]["block"]["blocks"] == "#minecraft:beds"
    assert adv["rewards"]["function"] == "monkey:quest/reward/home"
    reward = fn("reward/home")
    assert "scoreboard players set @s rq.home 1" in reward and "advancement revoke @s only monkey:quest/home" in reward


# ---------------------------------------------------------------- the wiring


def test_the_wardrobe_runs_the_quest():
    files = pack()
    load = body(files["data/monkey/function/wardrobe/load.mcfunction"])
    second = body(files["data/monkey/function/wardrobe/second.mcfunction"])
    tick = files["data/monkey/function/wardrobe/tick.mcfunction"]
    assert "function monkey:quest/load" in load
    new_day = next(i for i, line in enumerate(second) if "wardrobe/new_day" in line)
    assert second.index("function monkey:quest/second") > new_day   # rw.days is today's before it reads it
    assert "execute as @a[scores={quest=1..}] run function monkey:quest/use" in tick


def test_nothing_runs_before_the_launch_or_while_off():
    lines = body(fn("second"))
    assert lines[0] == "scoreboard players enable @a quest"
    assert lines[1] == "execute unless score #on rq matches 1 run return 0"
    assert lines[2] == f"execute unless score {challenges.LAUNCHED} matches 1 run return 0"
    assert all("quest/join" in x or "quest/check" in x for x in lines[3:])
    # Only players taking part are checked; everyone else costs the selector.
    assert lines[-1] == f"execute as @a[scores={{rq.state={quest.ON}}}] run function monkey:quest/check"


def test_veterans_are_never_signed_up():
    join = body(fn("join"))
    assert join[0] == f"scoreboard players set @s rq.state {quest.NOT_IN}"
    assert join[1] == "execute if score @s rw.playbase matches 1.. run return 0"
    assert join[2] == f"execute unless score @s rw.days matches ..{quest.ENROLL_DAYS} run return 0"
    assert join[3] == f"scoreboard players set @s rq.state {quest.ON}"
    assert sum(" tellraw @s " in f" {x}" for x in join) == 1


def test_reminders_are_once_a_day_and_stop():
    check = fn("check")
    assert "execute unless score @s rq.day = #today rw.day run function monkey:quest/remind" in check
    remind = body(fn("remind"))
    assert remind[0] == "scoreboard players operation @s rq.day = #today rw.day"
    assert remind[1] == f"execute unless score @s rw.days matches ..{quest.REMIND_DAYS} run return 0"


def test_a_step_done_stays_done_and_the_last_gives_the_skin():
    check = fn("check")
    for s in quest.STEPS:
        objective, n = s["score"]
        assert (f"execute unless score @s {quest.done_score(s)} matches 1.. if score @s {objective} matches {n}.. "
                f"run function monkey:quest/step/{s['id']}") in check
        step = fn(f"step/{s['id']}")
        assert f"scoreboard players set @s {quest.done_score(s)} 1" in step
        assert f"matches {len(quest.STEPS)}.. run return run function monkey:quest/finish" in step
    finish = fn("finish")
    assert f"scoreboard players set @s rq.state {quest.DONE}" in finish
    assert f"scoreboard players set @s {quest.REWARD} 1" in finish


def test_hide_and_show_again():
    use = fn("use")
    assert f"matches {quest.HIDE} if score @s rq.state matches {quest.ON} run function monkey:quest/hide" in use
    assert f"matches {quest.SHOW} if score @s rq.state matches {quest.HIDDEN} run scoreboard players set @s " \
           f"rq.state {quest.ON}" in use
    assert use.rstrip().endswith("scoreboard players enable @s quest")
    assert f"scoreboard players set @s rq.state {quest.HIDDEN}" in fn("hide")


def test_the_menu_fits_open_chat():
    from test_wardrobe import chat_lines
    files = pack()
    # An over-count (both halves of each step's done/not-done pair, every early return): still under 20.
    assert chat_lines(files, "quest/menu") <= 20


def test_the_launch_clears_test_play_once():
    launch = body(fn("launch"))
    assert launch[0] == f"execute if score {challenges.LAUNCHED} matches 1 run return 0"
    for o, crit in quest.objectives():
        if crit == "dummy" and o != quest.OBJ:
            assert f"scoreboard players reset * {o}" in launch, o
    assert f"execute if score #season rw.day matches 1 run scoreboard players reset * {quest.REWARD}" in launch
    ch = body(pack()["data/monkey/function/challenges/launch.mcfunction"])
    assert ch.index("function monkey:quest/launch") < ch.index(f"scoreboard players set {challenges.LAUNCHED} 1")


def test_the_switch():
    load = fn("load")
    assert f"execute unless score #on rq matches 0.. run scoreboard players set #on rq {quest.QUEST_ON}" in load
    assert "scoreboard players set #on rq 1" in fn("on") and "scoreboard players set #on rq 0" in fn("off")
    seasons = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8")
    assert "function monkey:quest/off" in seasons and "function monkey:quest/on" in seasons


# ---------------------------------------------------------------- the skin


def test_pathfinder_is_added_at_the_end_so_no_trigger_value_moves():
    values = {s["id"]: value for value, _, s in wardrobe.skins()}
    assert values["twinmoon"] == wardrobe.FIRST_BLADE + 18 and values["pathfinder"] == wardrobe.FIRST_BLADE + 19
    assert wardrobe.BLADES[-1]["unlock"] == (quest.REWARD, 1)
    assert wardrobe.page(wardrobe.BLADES[-1]["unlock"]) == quest.WARDROBE_PAGE
    assert quest.REWARD in wardrobe.NOTIFY


def test_veterans_never_see_pathfinder_locked():
    menu = pack()["data/monkey/function/wardrobe/menu.mcfunction"]
    locked = [x for x in menu.splitlines() if x.startswith("execute unless") and '"text":"Pathfinder"' in x]
    assert len(locked) == 1 and f" if score @s rq.state matches {quest.ON}.. run tellraw" in locked[0]
