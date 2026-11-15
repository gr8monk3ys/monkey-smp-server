# Monkey SMP patch (charged_tick): run as a cube on its button. The block has one marker, in its middle, marked as
# kept for the next tick; one is made if there is none (a new button, or a marker killed by a command or a cleanup,
# which would otherwise leave the button behind for good).
execute align xyz positioned ~0.5 ~0.5 ~0.5 unless entity @e[type=minecraft:marker,tag=sulfur_cube_dinamic_charge,distance=..0.01] run summon minecraft:marker ~ ~ ~ {Tags:["sulfur_cube_dinamic_charge"]}
execute align xyz positioned ~0.5 ~0.5 ~0.5 as @e[type=minecraft:marker,tag=sulfur_cube_dinamic_charge,distance=..0.01] run tag @s add sulfur_cube_charge_kept
