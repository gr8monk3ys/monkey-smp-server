"""Rule 5's guard, shared by every kill that earns something: a kill on a player who respawned less than
FRESH_MINUTES ago counts for nothing (docs/RULES.md, rule 5: no naked killing).

Wars (tools/diplomacy.py: the war score and the second count in the Kills column) and the wanted board
(tools/wanted.py: bounty claims) put fresh_victim_excluded() in their kill advancement's victim conditions, so
such a kill never fires them. It reads Minecraft's own statistic, time_since_death: ticks the player has been
alive since they last died, counted only while they are online and alive (time on the death screen doesn't
count), and reset as they die, after the killer's advancement has looked at it. No score or timer to keep: the
statistic is always there, and a player who has never died has been alive since their first join, so a
brand-new player counts as fresh for their first FRESH_MINUTES too (rule 26's grace covers them anyway).

This file is the same in every branch that uses it, so they merge in any order. Stdlib only.
"""

FRESH_MINUTES = 10
FRESH_TICKS = FRESH_MINUTES * 60 * 20
STAT = "minecraft:time_since_death"


def fresh(entity: str = "this") -> dict:
    """An entity condition (26.x shape): true for a player alive less than FRESH_MINUTES since their last death."""
    return {"type": "minecraft:entity_properties", "entity": entity, "predicate": {
        "minecraft:type_specific/player": {"stats": [
            {"type": "minecraft:custom", "stat": STAT, "value": {"max": FRESH_TICKS - 1}}]}}}


def fresh_victim_excluded(entity: str = "this") -> dict:
    """The term a kill advancement adds to its victim's conditions: the victim isn't fresh()."""
    return {"type": "minecraft:inverted", "term": fresh(entity)}
