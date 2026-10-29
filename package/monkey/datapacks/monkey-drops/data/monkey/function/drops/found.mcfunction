# Run at the spot's surface: announce it, count down.
summon minecraft:marker ~ ~ ~ {Tags:["dr.spot"]}
execute store result storage monkey:drops spot.y int 1 run data get entity @e[type=minecraft:marker,tag=dr.spot,limit=1] Pos[1]
execute store result score #night dr run data get storage monkey:drops night
scoreboard players operation #chests dr = #online dr
scoreboard players operation #chests dr /= #min dr
execute if score #chests dr matches ..0 run scoreboard players set #chests dr 1
execute if score #chests dr matches 4.. run scoreboard players set #chests dr 3
execute if score #meteor dr matches 1 run scoreboard players set #chests dr 1
scoreboard players set #state dr 2
scoreboard players set #timer dr 600
execute if score #meteor dr matches 1 run scoreboard players set #timer dr 300
bossbar add monkey:drop {"text":"","color":"gold","extra":[{"nbt":"name","storage":"monkey:drops","interpret":true}]}
bossbar set monkey:drop color yellow
execute if score #meteor dr matches 1 run bossbar set monkey:drop color purple
execute store result bossbar monkey:drop max run scoreboard players get #timer dr
execute store result bossbar monkey:drop value run scoreboard players get #timer dr
bossbar set monkey:drop players @a
bossbar set monkey:drop visible true
execute unless score #meteor dr matches 1 run tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"monkey:drops","interpret":true},": "]},{"text":"it lands at ","color":"yellow"},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":" in 10 minutes, with ","color":"yellow"},{"score":{"name":"#chests","objective":"dr"},"color":"aqua"},{"text":" chest(s) of supplies. First come, first served; the usual rules apply out there.","color":"yellow"}]
execute if score #meteor dr matches 1 run tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"monkey:drops","interpret":true},": "]},{"text":"something is falling out of the sky. It comes down at ","color":"yellow"},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":" in 5 minutes: one chest, with more in it than a supply drop. First come, first served; the usual rules apply out there.","color":"yellow"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 0.7
