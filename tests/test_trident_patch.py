"""The committed Trident All-Weather Channeling patch (ADR-0004): lightning only for the trident that just hit.

Upstream strikes every channeling trident that has ever dealt damage, including ones left lying in the
ground, so one hit called lightning down on every old trident nearby (docs/MAINTAINING.md, "Patches this pack
carries").
"""
import patches
from repo import REPO, load_json

SLUG = "trident-all-weather-channeling"
FUNCTION = "data/trident_all_weather_channeling/function/app/trident_hit_entity.mcfunction"


def committed() -> dict[str, bytes]:
    return patches.read(REPO.patches / SLUG)


def test_the_patch_replaces_only_the_hit_function():
    assert list(committed()) == [FUNCTION]


def test_only_the_nearest_flying_trident_is_struck():
    text = committed()[FUNCTION].decode("utf-8")
    selector = next(line for line in text.splitlines() if line.startswith("execute as @e[type=trident"))
    assert "inGround:0b" in selector
    assert "limit=1" in selector
    assert "sort=nearest" in selector


def test_the_manifest_pins_the_patch_to_the_mod_jar():
    entry = next(e for e in load_json(REPO.realms / "manifest.json")["mods"] if e["slug"] == SLUG)
    assert entry["patch"] == patches.reference(SLUG, entry["hashes"]["sha512"])
