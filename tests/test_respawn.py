"""Rule 5's guard (tools/respawn.py): a kill on a player who respawned less than 10 minutes ago earns nothing."""
import respawn


def test_fresh_is_under_ten_minutes_of_life_since_the_last_death():
    assert respawn.FRESH_MINUTES == 10 and respawn.FRESH_TICKS == 12000
    cond = respawn.fresh()
    assert cond["type"] == "minecraft:entity_properties" and cond["entity"] == "this"
    [stat] = cond["predicate"]["minecraft:type_specific/player"]["stats"]
    assert stat == {"type": "minecraft:custom", "stat": "minecraft:time_since_death", "value": {"max": 11999}}


def test_the_guard_is_the_inverse_of_fresh():
    assert respawn.fresh_victim_excluded() == {"type": "minecraft:inverted", "term": respawn.fresh()}
    assert respawn.fresh_victim_excluded("killer")["term"]["entity"] == "killer"
