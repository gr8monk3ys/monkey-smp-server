"""The 3.1.0 speed patches (docs/MAINTAINING.md, "Patches this pack carries") keep the behaviour a play test checked.

Each one is the upstream datapack function with its expensive part guarded, so what can go wrong is a guard that
stops something happening: these pin the cases that matter.
"""
import json

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
    for slug in ("amethyst-nether", "dynamic-lights", "silvers_strength-restrictions-season-5",
                 "silvers_strength-smp-season-5", "silvers_effects-library", "warden-with-loot"):
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


def test_bombs_arm_in_every_entity_that_can_hold_one():
    lines = commands(patched("amethyst-nether", "data/an/function/timer/tick.mcfunction"))
    arming = [line for line in lines if line.endswith("function an:items/bomb/add_marker")]
    kinds = {line.split("@e[type=minecraft:", 1)[1].split(",", 1)[0] for line in arming}
    assert kinds == {"snowball", "item", "item_frame", "glow_item_frame"}


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
