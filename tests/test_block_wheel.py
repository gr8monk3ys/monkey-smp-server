import json

import pytest

import block_wheel as wheel


def test_pool_is_sorted_and_unique():
    pool = wheel.load_pool()
    assert pool == sorted(set(pool))
    assert len(pool) > 1000


@pytest.mark.parametrize("block", [
    "bedrock", "spawner", "trial_spawner", "command_block", "chain_command_block", "barrier", "light",
    "reinforced_deepslate", "budding_amethyst", "end_portal_frame", "infested_stone", "petrified_oak_slab",
    "end_stone", "end_stone_bricks", "purpur_block", "chorus_flower", "end_rod", "dragon_egg", "shulker_box",
    "red_shulker_box", "suspicious_sand", "farmland", "dirt_path", "player_head",
])
def test_pool_leaves_out_what_survival_cant_get_before_the_end(block):
    assert block not in wheel.load_pool()
    assert not wheel.eligible(block)


@pytest.mark.parametrize("block", ["stone", "daylight_detector", "lightning_rod", "light_blue_wool", "beacon",
                                   "ender_chest", "sponge", "wither_skeleton_skull", "obsidian"])
def test_pool_keeps_hard_but_fair_blocks(block):
    assert block in wheel.load_pool()


def test_draw_is_repeatable_and_has_no_repeats():
    pool = wheel.load_pool()
    first = wheel.draw("S1 launch", pool)
    assert first == wheel.draw("S1 launch", pool)
    assert first == ["polished_granite", "red_bed", "stripped_warped_hyphae"]
    assert wheel.draw("S1 launch!", pool) != first
    assert len(set(wheel.draw("x", ["a", "b", "c"], 3))) == 3


def test_draw_refuses_more_spins_than_blocks():
    with pytest.raises(ValueError):
        wheel.draw("x", ["a"], 2)


def test_build_pool_from_reports(tmp_path):
    (tmp_path / "registries.json").write_text(json.dumps({"minecraft:item": {"entries": {
        "minecraft:stone": {}, "minecraft:bedrock": {}, "minecraft:diamond": {}, "minecraft:end_rod": {}}}}))
    (tmp_path / "blocks.json").write_text(json.dumps(
        {"minecraft:stone": {}, "minecraft:bedrock": {}, "minecraft:end_rod": {}, "minecraft:water": {}}))
    assert wheel.build_pool(tmp_path) == ["stone"]


def test_tellraw_names_blocks_in_the_players_language():
    out = wheel.tellraw("s", ["stone"])
    assert out.startswith("tellraw @a ")
    assert {"translate": "block.minecraft.stone", "color": "green"} in json.loads(out.removeprefix("tellraw @a "))
