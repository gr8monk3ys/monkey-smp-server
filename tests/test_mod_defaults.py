"""The mod configs in package/monkey/defaults keep the rules they were written for.

They are copied onto a server only when the file is missing (Install-Defaults), so these are the
settings a fresh install starts with (docs/ADMIN.md, "Mod settings").
"""
import tomllib

from repo import REPO

CONFIG = REPO.monkey / "defaults" / "config"

# Dungeons and Taverns' own enchantments (namespace nova_structures). Rule B18: event rewards only.
DNT_ENCHANTMENTS = {
    "aerials_bane", "antidote", "conductivity_curse", "ghasted", "gravity", "hydro_veil", "illagers_bane",
    "multishot", "outreach", "photosynthesis", "piercing", "power", "spiteful", "swift_soar", "traveler",
    "wax_wings", "wither_coated"}


def properties(path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


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
