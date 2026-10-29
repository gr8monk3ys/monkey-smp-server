scoreboard players remove #timer dr 1
scoreboard players operation #mins dr = #timer dr
scoreboard players add #mins dr 59
scoreboard players operation #mins dr /= #60 dr
execute store result bossbar monkey:drop value run scoreboard players get #timer dr
bossbar set monkey:drop players @a
bossbar set monkey:drop name [{"text":"","color":"red","extra":[{"nbt":"name","storage":"monkey:drops","interpret":true}," at "]},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":": despawns in ","color":"red"},{"score":{"name":"#mins","objective":"dr"},"color":"white"},{"text":" min","color":"red"}]
# A broken chest is done; an emptied one goes at once.
execute as @e[type=minecraft:marker,tag=dr.chest] at @s unless block ~ ~ ~ minecraft:chest run kill @s
# (A drop that landed before 2.8.0 keeps its loot table, and no items, until someone opens it.)
execute as @e[type=minecraft:marker,tag=dr.chest] at @s unless data block ~ ~ ~ LootTable unless data block ~ ~ ~ Items[0] run function monkey:drops/emptied
execute unless entity @e[type=minecraft:marker,tag=dr.chest] run return run function monkey:drops/looted
execute if score #timer dr matches 300 run tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"monkey:drops","interpret":true},": "]},{"text":"5 minutes until the chests at ","color":"yellow"},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":" despawn.","color":"yellow"}]
execute if score #timer dr matches ..0 run function monkey:drops/expire
