# Run at the spot's surface: announce it, count down.
summon minecraft:marker ~ ~ ~ {Tags:["dr.spot"]}
execute store result storage realms:drops spot.y int 1 run data get entity @e[type=minecraft:marker,tag=dr.spot,limit=1] Pos[1]
execute store result score #night dr run data get storage realms:drops night
scoreboard players operation #chests dr = #online dr
scoreboard players operation #chests dr /= #min dr
execute if score #chests dr matches ..0 run scoreboard players set #chests dr 1
execute if score #chests dr matches 4.. run scoreboard players set #chests dr 3
scoreboard players set #state dr 2
scoreboard players set #timer dr 600
bossbar add realms:drop {"text":"Supply drop","color":"gold"}
bossbar set realms:drop color yellow
bossbar set realms:drop max 600
bossbar set realms:drop value 600
bossbar set realms:drop players @a
bossbar set realms:drop visible true
tellraw @a ["",{"text":"Supply drop: ","color":"gold","bold":true},{"text":"it lands at ","color":"yellow"},{"nbt":"spot.x","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"realms:drops","color":"aqua"},{"text":" in 10 minutes, with ","color":"yellow"},{"score":{"name":"#chests","objective":"dr"},"color":"aqua"},{"text":" chest(s) of supplies. First come, first served; the usual rules apply out there.","color":"yellow"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 0.7
