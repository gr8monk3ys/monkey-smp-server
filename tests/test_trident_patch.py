"""The committed Trident All-Weather Channeling patch (ADR-0004): lightning only for the trident that just hit.

Upstream strikes every channeling trident that has ever dealt damage, including ones left lying in the
ground, so one hit called lightning down on every old trident nearby. Its lightning isn't damage a player
causes, so PvP grace and the spawn claim don't stop it either: the patch strikes nothing near spawn or near a
player in grace (docs/MAINTAINING.md, "Patches this pack carries").
"""
import patches
from repo import REPO, load_json

SLUG = "trident-all-weather-channeling"
FUNCTIONS = "data/trident_all_weather_channeling/function/app/"
HIT = FUNCTIONS + "trident_hit_entity.mcfunction"
STRIKE = FUNCTIONS + "summon_lightning.mcfunction"


def committed() -> dict[str, bytes]:
    return patches.read(REPO.patches / SLUG)


def text(path: str) -> str:
    return committed()[path].decode("utf-8")


def test_the_patch_replaces_only_the_two_functions():
    assert sorted(committed()) == sorted([HIT, STRIKE])


def test_only_the_attackers_own_flying_trident_is_marked():
    hit = text(HIT)
    assert "tag @s add tawc.attacker" in hit
    assert "on owner if entity @s[tag=tawc.attacker]" in hit
    assert "inGround:0b" in hit
    assert "distance=..128" in hit
    assert "tag=!tawc.done" in hit
    assert "lightning_bolt" not in hit


def test_the_strike_runs_a_tick_later_from_the_server():
    assert "schedule function trident_all_weather_channeling:app/summon_lightning 1t replace" in text(HIT)


def test_no_strike_near_spawn_or_a_player_in_grace():
    strike = text(STRIKE)
    assert "positioned ~-64 -64 ~-64 as @e[type=minecraft:trident,tag=tawc.hit,dx=128,dy=384,dz=128]" in strike
    assert "as @a[distance=..6]" in strike
    assert "armor.body *[custom_data~{monkey_grace:{}}]" in strike
    lines = strike.splitlines()
    summon = next(i for i, line in enumerate(lines) if "summon minecraft:lightning_bolt" in line)
    assert all("remove tawc.hit" not in line for line in lines[summon:-1])


def test_a_trident_is_struck_once():
    strike = text(STRIKE)
    assert strike.index("add tawc.done") < strike.index("summon minecraft:lightning_bolt")
    assert strike.rstrip().endswith("tag @e[type=minecraft:trident,tag=tawc.hit] remove tawc.hit")


def test_the_manifest_pins_the_patch_to_the_mod_jar():
    entry = next(e for e in load_json(REPO.monkey / "manifest.json")["mods"] if e["slug"] == SLUG)
    assert entry["patch"] == patches.reference(SLUG, entry["hashes"]["sha512"])
