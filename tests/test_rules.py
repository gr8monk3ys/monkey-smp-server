import json
import tomllib

import rules
from repo import REPO


def test_committed_packs_match_the_generator():
    assert rules.differences(REPO) == [], "run python tools/rules.py"


def test_formats_and_vanilla_lists_follow_the_server_minecraft_version():
    # DATA_FORMAT and VANILLA_NON_TREASURE are 26.3's; a Minecraft update must re-check them.
    assert REPO.load_manifest()["minecraft"] == rules.MINECRAFT


def test_fire_aspect_and_flame_are_out_of_every_source():
    data = rules.rules_files()
    tag = json.loads(data["data/minecraft/tags/enchantment/non_treasure.json"])
    assert tag["replace"] is True
    assert not set(rules.BANNED_ENCHANTMENTS) & set(tag["values"])
    # Everything else vanilla had is still there.
    assert len(tag["values"]) == len(rules.VANILLA_NON_TREASURE) - len(rules.BANNED_ENCHANTMENTS)
    for name in ("fire_aspect", "flame"):
        enchantment = json.loads(data[f"data/minecraft/enchantment/{name}.json"])
        assert enchantment["effects"] == {}
        assert enchantment["supported_items"] == []


def test_the_border_is_set_once_and_centred_on_spawn():
    data = rules.rules_files()
    load = data["data/realms/function/rules/load.mcfunction"]
    assert f"unless score #border {rules.OBJECTIVE} matches 1 run function realms:rules/border" in load
    border = data["data/realms/function/rules/border.mcfunction"]
    assert "worldborder center ~ ~" in border
    assert f"worldborder set {rules.BORDER}" in border
    assert f"scoreboard players set #border {rules.OBJECTIVE} 1" in border


def test_launch_closes_pvp_and_the_nether_then_opens_them_but_not_the_end():
    data = rules.rules_files()
    launch = data["data/realms/function/rules/launch.mcfunction"]
    over = data["data/realms/function/rules/launch_over.mcfunction"]
    assert "gamerule pvp false" in launch and "gamerule allow_entering_nether_using_portals false" in launch
    assert f"schedule function realms:rules/launch_over {rules.LAUNCH_SECONDS}s replace" in launch
    assert "gamerule pvp true" in over and "gamerule allow_entering_nether_using_portals true" in over
    assert "end_open" not in over


def test_every_function_a_pack_calls_exists():
    for files in (rules.rules_files(), rules.netherite_files()):
        defined = {p.removeprefix("data/realms/function/").removesuffix(".mcfunction")
                   for p in files if p.startswith("data/realms/function/")}
        called = set()
        for path, body in files.items():
            if path.endswith(".mcfunction"):
                words = body.split()
                called |= {w.removeprefix("realms:") for prev, w in zip(words, words[1:], strict=False)
                           if prev == "function" and w.startswith("realms:")}
            elif path.endswith("tags/function/load.json"):
                called |= {v.removeprefix("realms:") for v in json.loads(body)["values"]}
        assert called <= defined, called - defined


def test_only_netherite_armor_recipes_are_removed():
    data = rules.netherite_files()
    recipes = {p for p in data if p.startswith("data/minecraft/recipe/")}
    assert recipes == {f"data/minecraft/recipe/{i}_smithing.json" for i in rules.NETHERITE_ARMOR}
    for path in recipes:
        recipe = json.loads(data[path])
        assert recipe["template"] == rules.NEVER_TEMPLATE
        assert recipe["base"].startswith("minecraft:diamond_")
    tag = json.loads(data["data/realms/tags/item/netherite_armor.json"])["values"]
    assert not any("sword" in i or "axe" in i or "pickaxe" in i for i in tag)
    for slot in rules.ARMOR_SLOTS:
        assert f"data/realms/function/netherite/drop_{slot}.mcfunction" in data


def test_party_limit_default_is_four():
    text = (REPO.defaults / "config" / "openpartiesandclaims-server.toml").read_text(encoding="utf-8")
    assert "maxPartyMembers = 4" in text


def test_distant_horizons_sends_no_lods_it_built_itself():
    # B15: server-built LODs come from the real world, so they would carry every buried ore past AntiXray.
    config = tomllib.loads((REPO.defaults / "config" / "DistantHorizons.toml").read_text(encoding="utf-8"))
    assert config["server"] == {"synchronizeOnLoad": False, "enableRealTimeUpdates": False}
    assert config["common"]["worldGenerator"]["generatorPlan"] == "DISABLED"
