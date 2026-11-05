"""The committed Mace Limiter patch (tools/macelimiter_patch.py, ADR-0004) is the one-byte edit it claims to be, and
the Strength Restrictions nerf (its item modifier turns a mace into a poisonous potato) keeps the mace's id."""
import json

import pytest

import macelimiter_patch as ml
import patches
from repo import REPO, load_json

NERFED = "data/strength_restrictions/item_modifier/mace/nerfed.json"


def committed() -> dict[str, bytes]:
    return patches.read(REPO.patches / "mace-limiterrr")


def test_the_patch_replaces_only_the_item_stack_mixin():
    assert list(committed()) == [ml.CLASS]


def test_a_count_of_zero_no_longer_frees_a_slot():
    assert ml.releases_on_zero(committed()[ml.CLASS]) is False


def test_patching_an_already_patched_class_is_refused():
    with pytest.raises(SystemExit, match="Mace Limiter changed"):
        ml.patch_class(committed()[ml.CLASS])


def test_the_manifest_pins_the_patch_to_the_mace_limiter_jar():
    entry = next(e for e in load_json(REPO.monkey / "manifest.json")["mods"] if e["slug"] == "mace-limiterrr")
    assert entry["patch"] == patches.reference("mace-limiterrr", entry["hashes"]["sha512"])


def test_the_mace_nerf_merges_its_marker_into_custom_data():
    files = patches.read(REPO.patches / "silvers_strength-restrictions-season-5")
    modifiers = json.loads(files[NERFED])
    set_components = next(m for m in modifiers if m["function"] == "minecraft:set_components")
    assert "minecraft:custom_data" not in set_components["components"]
    merge = next(m for m in modifiers if m["function"] == "minecraft:set_custom_data")
    assert merge["tag"] == {"Strength_Restrictions+Disabled_Mace": {}}
