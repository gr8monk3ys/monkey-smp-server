import json
import re

import events
from repo import REPO

FILES = events.datapack_files()
FUNCTIONS = {k for k in FILES if k.endswith(".mcfunction")}


def fn(path: str) -> str:
    return FILES[f"{events.FN}/{path}.mcfunction"]


def test_committed_pack_matches_the_generator():
    assert events.differences(REPO) == [], "run python tools/events.py"


def test_pack_format_follows_the_server_minecraft_version():
    assert REPO.load_manifest()["minecraft"] == events.MINECRAFT


def test_every_called_function_exists():
    for path, body in FILES.items():
        for name in re.findall(rf"function {events.NS}:([\w/]+)", body):
            assert f"data/{events.NS}/function/{name}.mcfunction" in FUNCTIONS, f"{path} calls {name}"


def test_macro_lines_are_marked_and_marked_lines_are_macros():
    for path in FUNCTIONS:
        for line in FILES[path].splitlines():
            if line.startswith("#"):
                continue
            assert ("$(" in line) == line.startswith("$"), f"{path}: {line}"


def test_json_files_parse():
    for path, body in FILES.items():
        if path.endswith((".json", ".mcmeta")):
            json.loads(body)


def test_arena_keeps_strength_aside_and_lets_nothing_out():
    join, leave, tick = fn("arena/join"), fn("arena/leave"), fn("arena/tick")
    for slots in ("container.*", "armor.*", "weapon.offhand"):
        assert f"if items entity @s {slots} * run return" in join
    assert join.index("return") < join.index("tag @s add ev.arena")
    assert f"scoreboard players operation @s ev.strength = @s {events.LEVEL}" in join
    assert f"scoreboard players set @s {events.LEVEL} 3" in join
    assert "gamemode adventure @s" in join
    assert f"scoreboard players operation @s {events.LEVEL} = @s ev.strength" in leave
    assert "clear @s" in leave and "player.cursor" in leave and "gamemode survival @s" in leave
    # held at +3 every tick, withdrawals blocked, Strength items and drops destroyed, teleports taken out
    assert f"scoreboard players set @a[tag=ev.arena] {events.LEVEL} 3" in tick
    assert f"scoreboard players reset @a[tag=ev.arena] {events.WITHDRAW}" in tick
    assert events.STRENGTH_ITEM in tick
    assert "kill @e[type=minecraft:item" in tick
    assert "ev.away" in tick
    # kit gear can't be carried out: it is marked and cleared outside the arena, stripped from the ender
    # chest on the way out, and no bundle in the ender chest can hide it; other people's things are left alone
    assert f"clear @a[tag=!ev.arena] {events.KIT_ITEM}" in fn("tick")
    for i in range(27):
        for what in (events.KIT_ITEM, "#minecraft:bundles"):
            assert (f"if items entity @s enderchest.{i} {what} run item replace entity @s "
                    f"enderchest.{i} with minecraft:air") in leave
    assert "if items entity @s enderchest.* #minecraft:bundles run return" in join
    assert join.index("#minecraft:bundles") < join.index("tag @s add ev.arena")
    # in the arena: nothing but kit gear in hand, and nothing that holds items survives a tick
    assert f"clear @a[tag=ev.arena] {events.NOT_KIT_ITEM}" in tick
    assert tick.index(f"kill @e[type=#{events.NS}:holds_items") < tick.index("kill @e[type=minecraft:item")


def test_arena_deaths_leave_no_lootable_corpse():
    # player-death-corpses moves a dead player's kit onto a mannequin; it, its riders and its click box go
    # every tick and between rounds, before the item sweep that takes whatever they drop
    for body in (fn("arena/tick"), fn("arena/round")):
        for what in ("tag=player_corpses.corpse", "type=minecraft:interaction,tag=player_corpses.interaction"):
            line = next(line for line in body.splitlines() if f"kill @e[{what},distance=..$(size)]" in line)
            assert line.startswith("$execute in minecraft:overworld positioned $(px) $(py) $(pz) run")
            assert body.index(line) < body.index("kill @e[type=minecraft:item")


def test_holds_items_tag_covers_vehicles_and_pack_animals():
    tag = set(json.loads(FILES[f"data/{events.NS}/tags/entity_type/holds_items.json"])["values"])
    assert {"minecraft:chest_minecart", "minecraft:hopper_minecart", "minecraft:oak_chest_boat",
            "minecraft:bamboo_chest_raft", "minecraft:donkey", "minecraft:mule", "minecraft:llama",
            "minecraft:trader_llama"} <= tag


def test_strength_sync_removes_every_modifier_above_the_level():
    sync = fn("arena/strength_sync")
    for n in range(2, 6):
        assert (f"{events.LEVEL}=..{n - 1}}}] minecraft:attack_damage modifier remove "
                f"strength_smp:buff-level_{n}") in sync


def test_rejoining_takes_you_out_of_the_arena_and_takes_raid_flags():
    rejoined = fn("rejoined")
    assert "function realms:events/arena/leave" in rejoined
    assert "clear @s *[custom_data~{realms_flag:{}}]" in rejoined
    assert rejoined.index("#raid ev.state") < rejoined.index("clear @s")


def test_kits_follow_the_bans():
    for kit, items in events.KITS.items():
        body = fn(f"arena/kit/{kit}")
        names = [n for n, _ in items + events.FOOD] + list(events.ARMOR.values())
        assert not set(names) & events.BANNED, kit
        gear = [line for line in body.splitlines() if line.startswith(("give ", "item replace"))]
        assert gear and all("[custom_data={realms_kit:{}}]" in line for line in gear), f"{kit}: every item marked"
        for line in gear:
            assert "[" not in line.replace("[custom_data={realms_kit:{}}]", ""), f"{kit}: no other components"
        assert "unless entity @s[tag=ev.arena] run return" in body


def test_books_skip_banned_enchantments_and_stay_at_vanilla_max():
    assert not set(events.MAX_LEVEL) & events.NO_BOOK
    for ench, level in events.MAX_LEVEL.items():
        body = fn(f"book/{ench}")
        assert f'"minecraft:{ench}":{level}' in body
        assert "Monkey SMP event reward, Season $(season)" in body
    for banned in events.NO_BOOK:
        assert f"{events.FN}/book/{banned}.mcfunction" not in FILES


def test_anarchy_runs_90_minutes_then_a_10_minute_ceasefire_and_clears_contraband():
    assert [s for _, s, _, _ in events.TIMERS["anarchy"]] == [5400, 600]
    over = fn("anarchy/over")
    for item in ("totem_of_undying", "end_crystal", "enchanted_golden_apple"):
        assert f"clear @a minecraft:{item}" in over
    assert "ender_pearl" not in over
    second = fn("anarchy/second")
    end = "if score #anarchy ev.timer matches ..0 run return run function realms:events/anarchy"
    assert f"matches 1 {end}/phase2" in second
    assert f"matches 2 {end}/over" in second


def test_flags_survive_being_placed_and_broken():
    for color in events.COLORS:
        table = json.loads(FILES[f"data/minecraft/loot_table/blocks/{color}_banner.json"])
        entry = table["pools"][0]["entries"][0]
        assert entry["name"] == f"minecraft:{color}_banner"
        include = entry["modifier"]["include"]
        assert {"minecraft:custom_data", "minecraft:lore", "minecraft:banner_patterns"} <= set(include)
    assert len(events.COLORS) == 16
    stamp = fn("flag/stamp")
    assert '"realms_flag":{"id":"$(id)","n":$(n)}' in stamp
    assert '"type":"minecraft:set_count","count":1' in stamp


def test_help_lists_only_real_functions():
    assert fn("help").count("suggest_command") == len(events.HELP)
