# Back where they went in, in their game mode (also when a rule takes them out).
execute store result storage monkey:camera back.x double 0.01 run scoreboard players get @s cm.x
execute store result storage monkey:camera back.y double 0.01 run scoreboard players get @s cm.y
execute store result storage monkey:camera back.z double 0.01 run scoreboard players get @s cm.z
execute if score @s cm.dim matches 0 run data modify storage monkey:camera back.dim set value "overworld"
execute if score @s cm.dim matches 1 run data modify storage monkey:camera back.dim set value "the_nether"
execute if score @s cm.dim matches 2 run data modify storage monkey:camera back.dim set value "the_end"
function monkey:camera/back with storage monkey:camera back
execute if score @s cm.mode matches 0 run gamemode survival @s
execute if score @s cm.mode matches 1 run gamemode creative @s
execute if score @s cm.mode matches 2 run gamemode adventure @s
execute if score @s cm.mode matches 3 run gamemode spectator @s
scoreboard players set @s cm.in 0
tellraw @a ["",{"selector":"@s","color":"white"},{"text":" stopped filming.","color":"gray"}]
