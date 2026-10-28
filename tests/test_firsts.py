import json
import re

import pytest
from fake_world import FakeWorld
from nbt_writer import Ints

import firsts
import rules
import saved_world
from repo import REPO

FN = "data/realms/function/firsts"
FILES = firsts.datapack_files()
BANNED = ("totem", "end_crystal", "ender_pearl", "enchanted_golden_apple", "fire_aspect", "flame")


def advancement(fid: str) -> dict:
    return json.loads(FILES[f"data/realms/advancement/firsts/{fid}.json"])


def terms(fid: str) -> list[dict]:
    (criterion,) = advancement(fid)["criteria"].values()
    return criterion["conditions"]["player"]["terms"]


def fixed(t: dict) -> tuple[str, str, dict] | None:
    if t["type"] != "minecraft:int_value_check":
        return None
    return t["value"]["target"]["name"], t["value"]["score"], t["test"]


# ---------------------------------------------------------------- the milestones


def test_the_milestones_are_well_formed():
    ids = [m["id"] for m in firsts.MILESTONES]
    assert 10 <= len(ids) <= 14 and len(ids) == len(set(ids))
    for m in firsts.MILESTONES:
        assert re.fullmatch(r"[a-z]+", m["id"]), m["id"]
        assert 0 < len(m["name"]) <= firsts.NAME_MAX and m["about"], m["id"]
        assert m["name"][0].isupper() and firsts.phrase(m)[0].islower()
        body = json.dumps(m).lower()
        assert not any(b in body for b in BANNED), m["id"]


def test_each_milestone_has_its_advancement_and_functions():
    for m in firsts.MILESTONES:
        fid = m["id"]
        adv = advancement(fid)
        assert adv["rewards"] == {"function": f"realms:firsts/got/{fid}"}
        assert "display" not in adv   # hidden: no toast, no advancement screen entry
        (criterion,) = adv["criteria"].values()
        assert criterion["trigger"] == f"minecraft:{m['trigger']}"
        for k, v in m.get("conditions", {}).items():
            assert criterion["conditions"][k] == v
        for kind in ("got", "claim", "reopen"):
            assert f"{FN}/{kind}/{fid}.mcfunction" in FILES


def test_nothing_fires_before_the_launch_or_once_claimed():
    for m in firsts.MILESTONES:
        checks = [fixed(t) for t in terms(m["id"])]
        assert ("#launched", "rw.day", {"min": 1}) in checks
        assert (f"#{m['id']}", "rf", {"max": 0}) in checks
        got = FILES[f"{FN}/got/{m['id']}.mcfunction"].splitlines()
        body = [line for line in got if not line.startswith("#")]
        assert body[0] == f"advancement revoke @s only realms:firsts/{m['id']}"
        assert f"execute if score #{m['id']} rf matches 1.. run return 0" in body
        assert "execute unless score #launched rw.day matches 1 run return 0" in body
        assert "execute if entity @s[tag=ev.arena] run return 0" in body
        assert "execute unless entity @s[gamemode=!creative,gamemode=!spectator] run return 0" in body
        assert body[-1] == f"function realms:firsts/claim/{m['id']}"


def test_the_end_counts_only_while_open_and_netherite_only_after_rule_24():
    assert ("#end_open", rules.OBJECTIVE, {"min": 1}) in [fixed(t) for t in terms("end")]
    assert all(("#end_open", rules.OBJECTIVE, {"min": 1}) not in [fixed(t) for t in terms(m["id"])]
               for m in firsts.MILESTONES if m["id"] != "end")
    got = FILES[f"{FN}/got/netherite.mcfunction"]
    assert f"scoreboard players operation #age rf -= {rules.NETHERITE_BEAT} {rules.OBJECTIVE}" in got
    assert f"execute if score #age rf matches ..{firsts.NETHERITE_STALE} run return 0" in got
    assert got.index("#age rf matches") < got.index("function realms:firsts/claim/netherite")
    # The no-Netherite pack stamps the game time every second while it is on.
    second = rules.netherite_files()["data/realms/function/netherite/second.mcfunction"]
    assert f"execute store result score {rules.NETHERITE_BEAT} {rules.OBJECTIVE} run time query gametime" in second
    assert "schedule function realms:netherite/second 20t replace" in second
    # Worn, not just carried: all four armor slots.
    equipment = terms("netherite")[-1]["predicate"]["minecraft:equipment"]
    assert set(equipment) == {"head", "chest", "legs", "feet"}


def test_a_claim_is_kept_in_storage_and_scores_and_announced_to_everyone():
    claim = FILES[f"{FN}/claim/dragon.mcfunction"]
    body = [line for line in claim.splitlines() if not line.startswith("#")]
    assert body[0] == "execute if score #dragon rf matches 1.. run return 0"
    assert body[1] == "scoreboard players set #dragon rf 1"
    for line in ("scoreboard players add #claimed rf 1", "scoreboard players operation @s rf.dragon = #claimed rf",
                 "function realms:firsts/name",
                 "data modify storage realms:firsts held.dragon.name set from storage realms:firsts name",
                 "execute store result storage realms:firsts held.dragon.order int 1 run "
                 "scoreboard players get #claimed rf",
                 "execute store result storage realms:firsts held.dragon.week int 1 run "
                 "scoreboard players get #week rc.week"):
        assert line in body
    said = next(line for line in body if line.startswith("tellraw @a "))
    assert {"selector": "@s", "color": "yellow"} in json.loads(said[len("tellraw @a "):])
    assert "slay the dragon" in said
    assert any(line.startswith("title @a title ") for line in body)
    assert any(line.startswith("title @a subtitle ") for line in body)
    assert any("playsound" in line and line.startswith("execute as @a at @s") for line in body)


def test_the_name_is_read_from_a_player_head_and_never_left_over():
    name = [line for line in FILES[f"{FN}/name.mcfunction"].splitlines() if not line.startswith("#")]
    assert name[0] == 'data modify storage realms:firsts name set value ""'
    assert name[-1].startswith("kill @e[type=minecraft:item_display,tag=rf.name]")
    assert 'item.components."minecraft:profile".name' in name[3]
    table = json.loads(FILES["data/realms/loot_table/firsts/head.json"])
    (entry,) = table["pools"][0]["entries"]
    assert entry["name"] == "minecraft:player_head"
    assert entry["modifier"] == {"type": "minecraft:fill_player_head", "entity": "this"}


def test_the_first_launch_clears_test_play_and_a_later_one_nothing():
    launch = rules.rules_files()["data/realms/function/rules/launch.mcfunction"]
    assert launch.index("function realms:firsts/launch") < launch.index("function realms:challenges/launch")
    ours = [line for line in FILES[f"{FN}/launch.mcfunction"].splitlines() if not line.startswith("#")]
    assert ours == ["execute if score #launched rw.day matches 1 run return 0", "function realms:firsts/clear",
                    "function realms:firsts/clean"]
    clear = FILES[f"{FN}/clear.mcfunction"]
    assert "data remove storage realms:firsts held" in clear and "scoreboard players set #claimed rf 0" in clear
    for m in firsts.MILESTONES:
        assert f"function realms:firsts/reopen/{m['id']}" in clear
        reopen = FILES[f"{FN}/reopen/{m['id']}.mcfunction"]
        assert f"scoreboard players set #{m['id']} rf 0" in reopen
        assert f"scoreboard players reset * rf.{m['id']}" in reopen


def test_load_keeps_claims_and_the_trigger_lists_every_milestone():
    load = FILES[f"{FN}/load.mcfunction"]
    assert "scoreboard objectives add firsts trigger" in load
    for m in firsts.MILESTONES:
        assert f"scoreboard players add #{m['id']} rf 0" in load        # never set: a claim survives a reload
        assert f"scoreboard players set #{m['id']} rf" not in load
    assert "execute as @a[scores={firsts=1..}] run function realms:firsts/use" in FILES[f"{FN}/tick.mcfunction"]
    assert "scoreboard players enable @a firsts" in FILES[f"{FN}/second.mcfunction"]
    use = FILES[f"{FN}/use.mcfunction"]
    for m in firsts.MILESTONES:
        assert f"function realms:firsts/show/{m['id']}" in use


def test_nothing_counts_once_the_season_is_locked():
    for m in firsts.MILESTONES:
        assert ("#season_locked", "ev.state", {"max": 0}) in [fixed(t) for t in terms(m["id"])]
        got = FILES[f"{FN}/got/{m['id']}.mcfunction"]
        assert "execute if score #season_locked ev.state matches 1 run return 0" in got
        assert got.index("#season_locked") < got.index(f"function realms:firsts/claim/{m['id']}")


def test_the_reward_checks_the_end_is_open_too():
    got = FILES[f"{FN}/got/end.mcfunction"]
    assert f"execute unless score #end_open {rules.OBJECTIVE} matches 1.. run return 0" in got
    assert got.index("#end_open") < got.index("function realms:firsts/claim/end")
    assert all("#end_open" not in FILES[f"{FN}/got/{m['id']}.mcfunction"]
               for m in firsts.MILESTONES if m["id"] != "end")


def test_an_item_kept_from_test_play_never_claims_its_first():
    items = {m["id"]: m["item"] for m in firsts.MILESTONES if m.get("item")}
    assert items == {"diamond": "diamond", "debris": "ancient_debris", "mace": "mace", "elytra": "elytra"}
    clean = [line for line in FILES[f"{FN}/clean.mcfunction"].splitlines() if not line.startswith("#")]
    assert len(clean) == len(items)
    for (fid, item), line in zip(items.items(), clean, strict=True):
        assert line.startswith(f"execute as @a[tag=!rf.clean.{fid}] ")
        assert line.endswith(f" run tag @s add rf.clean.{fid}")
        for slot in ("container.*", "armor.*", "weapon.offhand"):   # all inventory_changed watches
            assert f"unless items entity @s {slot} minecraft:{item}" in line
        got = FILES[f"{FN}/got/{fid}.mcfunction"]
        assert f"execute unless entity @s[tag=rf.clean.{fid}] run return 0" in got
        assert got.index("rf.clean.") < got.index(f"function realms:firsts/claim/{fid}")
    for m in firsts.MILESTONES:
        if not m.get("item"):
            assert "rf.clean." not in FILES[f"{FN}/got/{m['id']}.mcfunction"]
    # Marked at the first launch (after the clear) for whoever is online, and every second after the launch.
    launch = [line for line in FILES[f"{FN}/launch.mcfunction"].splitlines() if not line.startswith("#")]
    assert launch[-2:] == ["function realms:firsts/clear", "function realms:firsts/clean"]
    assert ("execute if score #launched rw.day matches 1 run function realms:firsts/clean"
            in FILES[f"{FN}/second.mcfunction"])


def test_the_menu_reads_a_first_as_holders_does():
    show = [line for line in FILES[f"{FN}/show/vault.mcfunction"].splitlines() if not line.startswith("#")]
    assert show[0].startswith("execute unless score #vault rf matches 1.. run return run tellraw @s ")
    assert '"text":"  open"' in show[0]
    assert "execute if data storage realms:firsts held.vault{name:\"\"} run scoreboard players set #named rf 0" in show
    assert "execute if data storage realms:firsts held.vault{week:-1} run scoreboard players set #dated rf 0" in show
    lines = show[5:]
    assert len(lines) == 6 and not lines[-1].startswith("execute")   # the last one: no name, no week
    named = '{"storage":"realms:firsts","nbt":"held.vault.name","color":"yellow"}'
    online = '{"selector":"@a[scores={rf.vault=1..}]","color":"yellow"}'
    week = '"nbt":"held.vault.week"'
    for line in lines:
        dated = "if score #dated rf matches 1" in line
        assert (week in line) == dated, line
        if "if score #named rf matches 1" in line:
            assert named in line
        elif "if entity @a[scores={rf.vault=1..}]" in line:
            assert online in line and named not in line
        else:
            assert "a player now offline" in line and named not in line
    # Every other line returns, so the player sees exactly one.
    assert all(line.startswith("execute ") and " run return run tellraw @s " in line for line in lines[:-1])


def test_the_dragon_reopen_says_staff_must_respawn_it():
    reopen = FILES[f"{FN}/reopen/dragon.mcfunction"]
    assert "end crystals are banned" in reopen and "staff" in reopen and "claim/dragon" in reopen
    assert "respawn" not in FILES[f"{FN}/reopen/wither.mcfunction"]
    admin = (REPO.root / "docs" / "ADMIN.md").read_text(encoding="utf-8")
    assert "reopen/dragon" not in admin.split("## Server Firsts")[1].split("```")[1]   # not the example
    assert "respawn the dragon" in admin


def test_the_pack_is_generated_and_consistent():
    import datapacks
    assert "firsts" in datapacks.GENERATORS
    assert datapacks.differences(REPO, [firsts]) == []
    assert all(v.endswith("\n") and "\r" not in v for v in FILES.values())


# ---------------------------------------------------------------- reading the saved world


def claim(name, order, week):
    return {"name": name, "order": order, "week": week}


def world_with(tmp_path, held, scores=()):
    w = FakeWorld(tmp_path / "world").storage("realms", {"firsts": {"held": held, "name": "Alex"}})
    if scores:
        w.scores(*scores)
    return w.path


def test_holders_in_claim_order(tmp_path):
    world = world_with(tmp_path, {"dragon": claim("Steve", 3, 3), "diamond": claim("Alex", 1, 0),
                                  "nether": claim("Steve", 2, 0)})
    got = firsts.holders(world)
    assert [(f.id, f.player, f.order, f.week) for f in got] == [
        ("diamond", "Alex", 1, 0), ("nether", "Steve", 2, 0), ("dragon", "Steve", 3, 3)]
    assert got[2].milestone == "Slay the dragon"
    assert [f.id for f in firsts.claimed_in(got, 0)] == ["diamond", "nether"]
    assert firsts.claimed_in(got, 5) == []


def test_a_missing_name_comes_from_the_scores(tmp_path):
    world = world_with(tmp_path, {"bastion": claim("", 4, 1)}, scores=[("rf.bastion", "Kai", 4), ("rf", "#x", 1)])
    (f,) = firsts.holders(world)
    assert (f.id, f.player, f.order, f.week) == ("bastion", "Kai", 4, 1)
    # Scores alone (storage not saved yet): the week is unknown.
    world2 = FakeWorld(tmp_path / "w2").scores(("rf.elytra", "Mia", 7)).path
    (f,) = firsts.holders(world2)
    assert (f.id, f.player, f.order, f.week) == ("elytra", "Mia", 7, None)


def test_no_firsts_yet(tmp_path):
    assert firsts.holders(FakeWorld(tmp_path / "w").path) == []
    assert firsts.champion([]) is None
    assert firsts.holders(world_with(tmp_path, {})) == []


def test_a_week_of_minus_one_is_unknown_and_an_old_milestone_is_kept(tmp_path):
    world = world_with(tmp_path, {"nether": claim("Steve", 1, -1), "gone": claim("Alex", 2, 4)})
    got = firsts.holders(world)
    assert [(f.id, f.milestone, f.week) for f in got] == [("nether", "Enter the Nether", None), ("gone", "gone", 4)]


def test_the_champion_has_most_firsts_and_a_tie_goes_to_who_reached_it_first(tmp_path):
    world = world_with(tmp_path, {
        "diamond": claim("Alex", 1, 0), "nether": claim("Steve", 2, 0), "fortress": claim("Steve", 3, 1),
        "bastion": claim("Alex", 6, 1), "debris": claim("Kai", 7, 2)})
    table = firsts.standings(firsts.holders(world))
    assert [(s.player, s.count, s.reached) for s in table] == [("Steve", 2, 3), ("Alex", 2, 6), ("Kai", 1, 7)]
    assert firsts.champion(firsts.holders(world)).player == "Steve"


def test_command_storage_reads_26_3s_file_and_refuses_a_bad_one(tmp_path):
    w = FakeWorld(tmp_path / "w")
    assert saved_world.command_storage(w.path, "realms") is None
    w.storage("realms", {"firsts": {"held": {}}, "drops": {"night": 3}})
    assert saved_world.command_storage(w.path, "realms") == {"firsts": {"held": {}}, "drops": {"night": 3}}
    assert saved_world.command_storage(w.path, "other") is None
    w.storage("realms", {"firsts": Ints([1, 2])})
    with pytest.raises(ValueError, match="command_storage.dat"):
        saved_world.command_storage(w.path, "realms")


# ---------------------------------------------------------------- the command line


def test_champion_prints_the_title_commands(tmp_path, capsys):
    world = world_with(tmp_path, {"diamond": claim("Alex", 1, 0), "nether": claim("Steve", 2, 0)})
    assert firsts.main(["champion", str(world), "--season", "1"]) == 0
    out = capsys.readouterr().out
    assert "Tied on 1 with Steve: Alex reached it first." in out
    for line in ("team add title_pioneer_s1", "team modify title_pioneer_s1 color aqua",
                 'team modify title_pioneer_s1 prefix "[S1 Pioneer] "', "team join title_pioneer_s1 Alex"):
        assert f"  {line}\n" in out
    assert firsts.season_title(2)[0].startswith("title_")   # tools/season.py carries title_* teams
    assert firsts.title_commands("odd name", 1)[-1] == 'team join title_pioneer_s1 "odd name"'
    assert firsts.title_commands("Kai_2", 1)[-1] == "team join title_pioneer_s1 Kai_2"


def test_champion_with_no_firsts_and_list(tmp_path, capsys):
    empty = FakeWorld(tmp_path / "e").path
    assert firsts.main(["champion", str(empty), "--season", "1"]) == 1
    world = world_with(tmp_path, {"vault": claim("Alex", 1, 2)})
    assert firsts.main(["list", str(world)]) == 0
    out = capsys.readouterr().out
    assert "Open a trial vault" in out and "Alex  (#1  week 2)" in out
    assert f"1 of {len(firsts.MILESTONES)} claimed" in out
    assert firsts.main(["list", str(tmp_path / "missing")]) == 2
