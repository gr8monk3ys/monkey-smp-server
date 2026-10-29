"""The committed Loot Restock patch (tools/lootrestock_patch.py, ADR-0004) is the one-class edit it claims to be."""
import pytest

import lootrestock_patch as lr
import patches
from repo import REPO, load_json


def committed() -> dict[str, bytes]:
    return patches.read(REPO.patches / "lootrestock")


def test_the_patch_replaces_only_the_chest_interaction_handler():
    assert list(committed()) == [lr.CLASS]


def test_the_patched_handlers_no_longer_roll_loot_when_tracking_a_container():
    data = committed()[lr.CLASS]
    cf = lr.ClassFile(data)
    assert set(lr.METHODS) <= set(cf.code)
    assert lr.rolling_calls(data) == []


def test_patching_an_already_patched_class_is_refused():
    with pytest.raises(SystemExit, match="Loot Restock changed"):
        lr.patch_class(committed()[lr.CLASS])


def test_the_manifest_pins_the_patch_to_the_loot_restock_jar():
    entry = next(e for e in load_json(REPO.monkey / "manifest.json")["mods"] if e["slug"] == "lootrestock")
    assert entry["patch"] == patches.reference("lootrestock", entry["hashes"]["sha512"])
