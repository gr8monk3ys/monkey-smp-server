# Staff, standing at spawn in the Overworld: the spawn warp (and the board's, while its chunk isn't loaded).
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"Stand at spawn, in the Overworld.","color":"red"}
execute store result storage monkey:camera spawn.x int 1 run data get entity @s Pos[0]
execute store result storage monkey:camera spawn.z int 1 run data get entity @s Pos[2]
tellraw @s {"text":"Camera spawn point set here.","color":"green"}
