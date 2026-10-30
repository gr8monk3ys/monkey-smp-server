# As the new boss: its act (the kill advancement reads it), its attributes and its health.
tag @s remove bs.new
scoreboard players operation @s bs.id = #act bs
attribute @s minecraft:scale base set 2.0
attribute @s minecraft:armor base set 15
attribute @s minecraft:armor_toughness base set 6
attribute @s minecraft:attack_damage base set 14
attribute @s minecraft:knockback_resistance base set 0.8
attribute @s minecraft:movement_speed base set 0.3
attribute @s minecraft:follow_range base set 48
attribute @s minecraft:step_height base set 1.5
attribute @s minecraft:fall_damage_multiplier base set 0
effect give @s minecraft:fire_resistance infinite 0 true
function monkey:boss/health with storage monkey:boss at
