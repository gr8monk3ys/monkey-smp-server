"""The mod configs in package/monkey/defaults keep the rules they were written for.

They are copied onto a server only when the file is missing (Install-Defaults), so these are the
settings a fresh install starts with (docs/ADMIN.md, "Mod settings").
"""
from repo import REPO

CONFIG = REPO.monkey / "defaults" / "config"


def properties(path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


def test_loot_restock_refills_only_emptied_structure_chests_weekly():
    loot = properties(REPO.monkey / "defaults" / "lootrestock.properties")
    assert (loot["reset_time_value"], loot["reset_time_unit"], loot["reset_cron"]) == ("7", "days", "")
    assert loot["only_reset_when_empty"] == "true"
    assert loot["include_barrels"] == loot["include_item_frames"] == loot["include_vaults"] == "false"
