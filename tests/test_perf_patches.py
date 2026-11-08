"""The 3.1.0 speed patches (docs/MAINTAINING.md, "Patches this pack carries") keep the behaviour a play test checked.

Each one is the upstream datapack function with its expensive part guarded, so what can go wrong is a guard that
stops something happening: these pin the cases that matter.
"""
import json
import re

import patches
from repo import REPO, load_json

MACRO = "function s_inv_lib:macro/item_modify/with_existing"
SMP = "overlay_26.2/data/strength_smp/function/technical/main/"


def patched(slug, path):
    return patches.read(REPO.patches / slug)[path].decode("utf-8")


def commands(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def test_every_speed_patch_is_pinned_in_the_manifest():
    mods = {e["slug"]: e for e in load_json(REPO.monkey / "manifest.json")["mods"]}
    for slug in ("dynamic-lights", "silvers_strength-restrictions-season-5",
                 "silvers_strength-smp-season-5", "silvers_effects-library", "warden-with-loot",
                 "colorful-trims", "glowing-glow-squids", "sulfur-cube-expansion"):
        assert mods[slug]["patch"] == patches.reference(slug, mods[slug]["hashes"]["sha512"])


def test_macro_calls_only_run_when_a_slot_holds_the_item():
    restrictions = "data/strength_restrictions/function/technical/main/tick/public.mcfunction"
    files = [patched("silvers_strength-restrictions-season-5", restrictions),
             patched("silvers_strength-smp-season-5", SMP + "powers/spear.mcfunction"),
             patched("silvers_strength-smp-season-5", SMP + "enchant/main.mcfunction")]
    for text in files:
        calls = [line for line in commands(text) if MACRO in line]
        assert calls
        assert all(" if items entity @s " in line for line in calls)


def test_each_guard_tests_the_item_its_macro_edits():
    """A guard on the wrong item leaves the macro never running, and the banned item stays."""
    public = "data/strength_restrictions/function/technical/main/tick/public.mcfunction"
    files = [patched("silvers_strength-restrictions-season-5", public),
             patched("silvers_strength-smp-season-5", SMP + "powers/spear.mcfunction"),
             patched("silvers_strength-smp-season-5", SMP + "enchant/main.mcfunction")]
    for text in files:
        for line in commands(text):
            if MACRO in line:
                guarded = line.split(" if items entity @s ", 1)[1].split(" ", 1)[1].split(f" run {MACRO}", 1)[0]
                assert f"\"beginning_item\":'{guarded}'" in line


def test_each_guard_covers_all_the_slots_the_macro_edits():
    """The macro touches the hotbar, the inventory, the offhand and the armour: a missing slot keeps a banned item."""
    text = patched("silvers_strength-smp-season-5", SMP + "powers/spear.mcfunction")
    for slots in ("container.*", "weapon.offhand", "armor.*"):
        assert sum(f"if items entity @s {slots} " in line for line in commands(text)) == 7


def test_armor_and_sword_powers_stay_upstream():
    """A guard on the armor power's HurtTime read looked free and stopped its hit counter ever starting."""
    files = patches.read(REPO.patches / "silvers_strength-smp-season-5")
    assert not [path for path in files if path.endswith(("powers/armor.mcfunction", "powers/sword.mcfunction"))]


def test_fire_is_still_read_for_both_effects_that_use_it():
    tick = "overlay_26.2/data/s_effects_lib/function/technical/tick/public.mcfunction"
    text = patched("silvers_effects-library", tick)
    fire = [line for line in commands(text) if "store result score @s s_effects_lib+Fire" in line]
    effects = ["s_effects_lib+eternal_flame_duration", "s_effects_lib+undead_curse_duration"]
    assert sorted(line.split()[4] for line in fire) == effects


def test_tnt_is_counted_every_tick_and_a_fuse_ending_forces_a_light_pass():
    """A light block stops explosion damage, so lights must clear on time though they update every other tick."""
    lines = commands(patched("dynamic-lights", "data/dynamiclights/function/internal/main.mcfunction"))
    tnt = next(line for line in lines if "explosion_detection/tnt" in line)
    assert "$pass" not in tnt
    force = "execute if score $global ts.dl.tnt.fuse matches 1 run scoreboard players set $pass ts.dl.settings 0"
    assert lines.index(tnt) < lines.index(force) < next(i for i, line in enumerate(lines) if "tag=ts.dl.light" in line)


def test_warden_advancements_test_the_biome_before_reading_the_player():
    for name in ("spawn_warden", "trigger_sculk_shrieker"):
        text = patched("warden-with-loot", f"data/warden_with_loot/advancement/deep_dark/{name}.json")
        for crit in json.loads(text)["criteria"].values():
            first = crit["conditions"]["player"][0]
            assert first == {"condition": "minecraft:location_check", "predicate": {"biomes": "minecraft:deep_dark"}}


# The scan patches below fold many world-wide @e scans into one pass that runs the same function again as each
# entity it finds. The function is also the pack's tick function, run by the server with no entity, so the
# entity-only lines must never stop the server before it reaches its passes.
TRIMS = "data/colorful_trims/function/tick.mcfunction"
CUBES = "data/more_archetypes/function/tick.mcfunction"
EFFECTS_TICK = "overlay_26.2/data/s_effects_lib/function/technical/tick/private.mcfunction"
CUBE_ARCHETYPES = [
    "hot_air", "sticky", "extra_sticky", "shulker", "healing", "booster", "creepy", "potent", "potent", "anvil",
    "oven", "sonic", "barbed", "fragile", "fragile_panes", "small_explosive", "big_explosive", "dried_ghast",
    "dried_ghast", "propeller", "charged", "luminous_torch", "luminous_r_torch", "luminous_lantern",
    "boombox_running", "boombox", "bigger", "smaller", "cheaty", "cheaty"
]
DYES = ("red", "orange", "yellow", "green", "lime", "cyan", "light_blue", "blue", "purple", "magenta", "pink",
        "white", "light_gray", "gray", "black", "brown")


def world_scans(text):
    """Selectors that look at every loaded entity: @e with no distance limit."""
    found = re.findall(r"@e\[[^\]]*\]|@e(?!\[)", chr(10).join(commands(text)))
    return [s for s in found if "distance=" not in s]


def server_stops_at(text):
    """The first line that returns when the function runs with no entity, as a tick function does."""
    for i, line in enumerate(commands(text)):
        if " return" not in f" {line}" and not line.startswith("return"):
            continue
        conditions = re.findall(r"(if|unless) entity (@s(?:\[[^\]]*\])?)", line.split(" run ", 1)[0])
        if all(kind == "unless" for kind, _ in conditions):
            return i
    return None


def test_colorful_trims_scans_items_once_and_still_sets_every_dye():
    text = patched("colorful-trims", TRIMS)
    assert world_scans(text) == ["@e[type=minecraft:item]"]
    lines = commands(text)
    for color in DYES:
        hits = [line for line in lines if f"contents minecraft:{color}_dye run" in line]
        assert len(hits) == 1
        assert f'"minecraft:provides_trim_material":"colorful_trims:{color}"' in hits[0]
    pass_line = next(line for line in lines if line.startswith("execute as @e"))
    assert "#colorful_trims:dyes[!minecraft:provides_trim_material]" in pass_line
    assert pass_line.endswith("run function colorful_trims:tick")
    assert server_stops_at(text) is None


def test_colorful_trims_still_fixes_dyes_held_by_players():
    lines = commands(patched("colorful-trims", TRIMS))
    for slot in ("container.*", "player.cursor", "weapon.offhand"):
        dyes = "#colorful_trims:dyes[!minecraft:provides_trim_material]"
        assert f"execute as @a if items entity @s {slot} {dyes} run function colorful_trims:fix_dyes" in lines


def test_glow_squid_light_finds_its_new_marker_where_it_summoned_it():
    text = patched("glowing-glow-squids", "data/gsg/function/light.mcfunction")
    assert not world_scans(text)
    summon, search = commands(text)
    assert summon.startswith("execute align xyz positioned ~0.5 ~ ~0.5 run summon minecraft:marker ~ ~ ~ ")
    assert '"gsg.light"' in summon
    assert search.startswith("execute align xyz positioned ~0.5 ~ ~0.5 as @e[type=minecraft:marker,tag=gsg.light,")
    assert search.endswith("at @s run function gsg:search")


def test_sulfur_cubes_run_every_archetype_in_one_pass():
    text = patched("sulfur-cube-expansion", CUBES)
    assert len(world_scans(text)) == 5
    assert sum("@e[type=minecraft:sulfur_cube]" in line for line in commands(text)) == 1
    # Upstream 1.0's archetype checks, in its order.
    assert re.findall(r"if predicate more_archetypes:(\w+)", text) == CUBE_ARCHETYPES


def test_the_server_reaches_the_sulfur_cube_passes_and_cubes_reach_their_archetypes():
    lines = commands(patched("sulfur-cube-expansion", CUBES))
    stop = server_stops_at(chr(10).join(lines))
    passes = [i for i, line in enumerate(lines) if line.startswith("execute unless entity @s as @e")]
    assert len(passes) == 5
    assert stop is not None and max(passes) < stop
    assert lines[stop] == "execute unless entity @s[type=minecraft:sulfur_cube] run return 0"
    # A cube is not stopped by the mannequin block's guard.
    guard = next(line for line in lines if line.endswith("run return 0") and line.startswith("execute if entity @s "))
    assert "unless entity @s[type=minecraft:sulfur_cube]" in guard


def test_herobrine_still_faces_the_player_nearest_the_server_position():
    """Upstream turned the mannequin from the server's position (no `at @s`), so the pass must not add one."""
    lines = commands(patched("sulfur-cube-expansion", CUBES))
    assert "execute unless entity @s as @e[tag=temp_mannequin] run function more_archetypes:tick" in lines


def test_effects_library_flames_and_stun_boxes_run_every_step():
    text = patched("silvers_effects-library", EFFECTS_TICK)
    lines = commands(text)
    ages = [int(m) for m in re.findall(r'age:"(\d+)"', text)]
    assert ages == list(range(16))
    flame = "@e[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display]"
    stun = "@e[type=minecraft:interaction,tag=s_effects_lib+Stun_Interaction]"
    assert sum(flame in line for line in lines) == 1
    assert sum(stun in line for line in lines) == 1
    assert len(world_scans(text)) == 1 + 18 + 2  # every mob's effects, the 18 decreasers (one tick in 21), 2 passes
    assert server_stops_at(text) is None
    assert "advancement revoke @a only s_effects_lib:technical/tick" in lines
