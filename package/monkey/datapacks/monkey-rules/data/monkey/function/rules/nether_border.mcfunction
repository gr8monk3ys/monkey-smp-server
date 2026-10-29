# Runs as a marker at spawn (it exists only for this function).
execute store result storage monkey:rules border.x double 0.125 run data get entity @s Pos[0] 1
execute store result storage monkey:rules border.z double 0.125 run data get entity @s Pos[2] 1
kill @s
function monkey:rules/nether_border_at with storage monkey:rules border
execute in minecraft:the_nether run worldborder set 312.5
