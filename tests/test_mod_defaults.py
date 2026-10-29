"""The 2.8.0 mod configs in package/monkey/defaults keep the rules they were written for.

They are copied onto a server only when the file is missing (Install-Defaults), so these are the
settings a fresh install and the 2.8.0 upgrade start with (docs/ADMIN.md, "Mod settings").
"""
import tomllib

from repo import REPO, load_json

CONFIG = REPO.monkey / "defaults" / "config"

# Dungeons and Taverns' own enchantments (namespace nova_structures). Rule B18: event rewards only.
DNT_ENCHANTMENTS = {
    "aerials_bane", "antidote", "conductivity_curse", "ghasted", "gravity", "hydro_veil", "illagers_bane",
    "multishot", "outreach", "photosynthesis", "piercing", "power", "spiteful", "swift_soar", "traveler",
    "wax_wings", "wither_coated"}


def properties(path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


def test_carry_on_cannot_lift_players_chests_or_server_features():
    carry = load_json(CONFIG / "carryon-common.json")
    assert carry["settings"]["pickupPlayers"] is False
    tiles = set(carry["blacklist"]["forbiddenTiles"])
    # Supply drops are chests; a carried chest also skips the raid rules' container checks.
    assert {"minecraft:chest", "minecraft:trapped_chest", "minecraft:*_banner", "minecraft:*_wall_banner",
            "minecraft:trial_spawner", "minecraft:vault"} <= tiles
    entities = set(carry["blacklist"]["forbiddenEntities"])
    # The Guide and Town Crier are Easy NPCs; the standings board is text displays and markers.
    assert {"easy_npc:*", "minecraft:text_display", "minecraft:marker", "minecraft:interaction",
            "minecraft:chest_minecart", "minecraft:armor_stand"} <= entities


def test_loot_restock_refills_only_emptied_structure_chests_weekly():
    loot = properties(REPO.monkey / "defaults" / "lootrestock.properties")
    assert (loot["reset_time_value"], loot["reset_time_unit"], loot["reset_cron"]) == ("7", "days", "")
    assert loot["only_reset_when_empty"] == "true"
    assert loot["include_barrels"] == loot["include_item_frames"] == loot["include_vaults"] == "false"


def test_dungeons_and_taverns_books_come_from_events_only():
    config = tomllib.loads((CONFIG / "enchantmentdisabler" / "config.toml").read_text(encoding="utf-8"))
    disabled = dict(config["disabler"]["disabledEnchantmentsV2"])
    assert set(disabled) == {f"nova_structures:{name}" for name in DNT_ENCHANTMENTS}
    assert all(sources == {"table": False, "loot": False, "trade": False} for sources in disabled.values())


def test_minecarts_do_not_hurt_players():
    assert load_json(CONFIG / "ultimate_minecarts_server.json")["minecartDamageEnabled"] is False
