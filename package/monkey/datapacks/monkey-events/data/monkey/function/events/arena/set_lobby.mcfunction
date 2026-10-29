# Run standing at the arena's entrance: players join here and leave to here.
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"The arena has to be in the overworld.","color":"red"}
execute store result storage monkey:events arena.lx int 1 run data get entity @s Pos[0]
execute store result storage monkey:events arena.ly int 1 run data get entity @s Pos[1]
execute store result storage monkey:events arena.lz int 1 run data get entity @s Pos[2]
tellraw @s {"text":"Arena lobby set here.","color":"green"}
