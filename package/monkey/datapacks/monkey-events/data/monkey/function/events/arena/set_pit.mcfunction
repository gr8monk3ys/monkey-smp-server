# Run standing at the waiting room inside: players arrive and respawn here.
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"The arena has to be in the overworld.","color":"red"}
execute store result storage monkey:events arena.px int 1 run data get entity @s Pos[0]
execute store result storage monkey:events arena.py int 1 run data get entity @s Pos[1]
execute store result storage monkey:events arena.pz int 1 run data get entity @s Pos[2]
tellraw @s {"text":"Arena pit set here.","color":"green"}
