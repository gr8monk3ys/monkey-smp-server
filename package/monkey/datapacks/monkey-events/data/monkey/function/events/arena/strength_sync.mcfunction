# Removes the Strength mod's damage modifiers above the player's level; the mod adds the rest.
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_2
attribute @s[scores={Strength_SMP+Strength_Level=..2}] minecraft:attack_damage modifier remove strength_smp:buff-level_3
attribute @s[scores={Strength_SMP+Strength_Level=..3}] minecraft:attack_damage modifier remove strength_smp:buff-level_4
attribute @s[scores={Strength_SMP+Strength_Level=..4}] minecraft:attack_damage modifier remove strength_smp:buff-level_5
