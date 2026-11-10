"""Strength SMP's crossbow and armor ultimates undo what they do (docs/MAINTAINING.md, "Patches this pack carries").

Upstream left the crossbow ultimate's buff on the crossbow for good, never counted the armor ultimate down (so its
knockback immunity lasted until death, and so did its cooldown), and turned Armor players' diamond armor into
netherite one way, which rule 24 then took off them. These pin each fix.
"""
import json

import patches
from repo import REPO

SLUG = "silvers_strength-smp-season-5"
SMP = "overlay_26.2/data/strength_smp/"
ULT = 'minecraft:crossbow[minecraft:enchantments~[{enchantments:"strength_smp:crossbow_ult"}]]'


def patched(path):
    return patches.read(REPO.patches / SLUG)[SMP + path].decode("utf-8")


def commands(text):
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def test_the_crossbow_buff_comes_off_every_slot_once_the_ultimate_is_over():
    enchant = commands(patched("function/technical/main/enchant/main.mcfunction"))
    lines = [line for line in enchant if "crossbow_ult" in line]
    for slots in ("container.*", "weapon.offhand", "armor.*", "player.cursor"):
        line = next(line for line in lines if f"if items entity @s {slots} {ULT} " in line)
        assert line.startswith("execute unless score @s Strength_SMP+Crossbow-Ultimate_Duration matches 1.. ")
        assert "strength_smp:remove_enchants/crossbow_ult" in line
    assert len(lines) == 4


def test_the_table_clear_takes_the_crossbow_buff_off_too():
    modifiers = json.loads(patched("item_modifier/remove_enchants.json"))
    removed = {name for m in modifiers for name in m["enchantments"]}
    assert {"strength_smp:crossbow", "strength_smp:crossbow_ult"} <= removed


def test_the_armor_ultimate_counts_down_like_the_others():
    lines = commands(patched("function/technical/main/tick/public.mcfunction"))
    for objective in ("Armor-Ultimate_Duration", "Mace-Ultimate_Duration"):
        assert any(line.startswith("scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,"
                                   f"Strength_SMP+{objective}=1..}}]") for line in lines)
    assert any("Armor-Ultimate_Duration=..0,Strength_SMP+Armor-Ultimate_Cooldown=1..}] "
               "Strength_SMP+Armor-Ultimate_Cooldown 1" in line for line in lines)


def test_the_armor_ultimate_modifiers_come_off_for_every_player():
    """Removal lives in tick/public, which runs whatever the power, so a reroll can't keep it."""
    public = commands(patched("function/technical/main/tick/public.mcfunction"))
    removes = [line for line in public if " modifier remove " in line]
    for name in ("armor_ultimate-knockback_resistance", "armor_ultimate-explosion_knockback_resistance",
                 "shield_ultimate-explosion_knockback_resistance", "shield_ultimate-knockback_resistance"):
        line = next(line for line in removes if line.endswith(f"strength_smp:{name}"))
        assert "unless score @s Strength_SMP+Armor-Ultimate_Duration matches 1.." in line
    shared = next(line for line in removes if line.endswith("strength_smp:shield_ultimate-knockback_resistance"))
    assert "unless score @s Strength_SMP+Shield-Ultimate_Duration matches 1.." in shared


def test_the_armor_power_adds_only_its_own_modifiers_and_swaps_nothing():
    armor = commands(patched("function/technical/main/powers/armor.mcfunction"))
    changes = [line for line in armor if " modifier add " in line or " modifier remove " in line]
    ultimate = [line for line in changes if "strength_smp:armor_ultimate-" in line]
    assert len(ultimate) == 2 and all(" modifier add " in line for line in ultimate)
    assert all("strength_smp:armor_passive-" in line for line in changes if line not in ultimate)
    assert not [line for line in armor if "s_inv_lib:macro/item_modify" in line or "netherite" in line]


def test_the_armor_power_keeps_upstreams_hit_counter():
    """A guard on the HurtTime read once stopped the hit counter ever starting (tests/test_perf_patches.py)."""
    armor = commands(patched("function/technical/main/powers/armor.mcfunction"))
    assert armor[:3] == [
        "scoreboard players set @s[nbt={HurtTime:9s}] Strength_SMP+Damaged_Counter_Duration 60",
        "scoreboard players remove @s[scores={Strength_SMP+Damaged_Counter_Duration=1..}] "
        "Strength_SMP+Damaged_Counter_Duration 1",
        "scoreboard players set @s[scores={Strength_SMP+Damaged_Counter_Duration=0}] Strength_SMP+Damaged_Counter 0",
    ]


def test_the_armor_ultimate_takes_a_full_diamond_or_netherite_set():
    terms = json.loads(patched("predicate/armor_check.json"))["terms"]
    slots = {}
    for term in terms:
        slots.update(term["predicate"]["minecraft:slots"])
    assert set(slots) == {"armor.head", "armor.chest", "armor.legs", "armor.feet"}
    for slot, piece in zip(("armor.head", "armor.chest", "armor.legs", "armor.feet"),
                           ("helmet", "chestplate", "leggings", "boots"), strict=True):
        assert slots[slot]["items"] == [f"minecraft:diamond_{piece}", f"minecraft:netherite_{piece}"]



PIECES = {"head": "helmet", "chest": "chestplate", "legs": "leggings", "feet": "boots"}
PASSIVE = (("armor_toughness", "1"), ("knockback_resistance", "0.1"))
OFF = "strength_smp.armor_passive.off"


def test_the_armor_passive_follows_each_worn_diamond_piece():
    """Instead of upstream's netherite swap: netherite's extra stats while each diamond piece is worn."""
    armor = commands(patched("function/technical/main/powers/armor.mcfunction"))
    assert "tag @s add strength_smp.armor_passive" in armor
    for slot, piece in PIECES.items():
        worn = f"items entity @s armor.{slot} minecraft:diamond_{piece} run attribute @s minecraft:"
        for attribute, amount in PASSIVE:
            name = f"strength_smp:armor_passive-{slot}-{attribute}"
            assert f"execute if {worn}{attribute} modifier add {name} {amount} add_value" in armor
            assert f"execute unless {worn}{attribute} modifier remove {name}" in armor


def test_the_armor_passive_comes_off_on_a_new_power_and_at_death():
    """tick/public runs whatever the power; the clear runs before death_resets zeroes the death count."""
    public = commands(patched("function/technical/main/tick/public.mcfunction"))
    start = public.index("execute if entity @s[tag=strength_smp.armor_passive] unless score @s "
                         f"Strength_SMP+Selected_Weapon_ID matches 9 run tag @s add {OFF}")
    assert public[start + 1] == f"tag @s[tag=strength_smp.armor_passive,scores={{Strength_SMP+Death=1..}}] add {OFF}"
    removes = public[start + 2:start + 10]
    assert removes == [f"attribute @s[tag={OFF}] minecraft:{attribute} modifier remove "
                       f"strength_smp:armor_passive-{slot}-{attribute}" for slot in PIECES for attribute, _ in PASSIVE]
    assert public[start + 10:start + 12] == [f"tag @s[tag={OFF}] remove strength_smp.armor_passive",
                                             f"tag @s[tag={OFF}] remove {OFF}"]
    resets = next(i for i, line in enumerate(public) if "death_resets" in line and "Death=1.." in line)
    assert start + 11 < resets
