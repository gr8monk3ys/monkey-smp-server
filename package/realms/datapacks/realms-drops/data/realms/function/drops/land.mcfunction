scoreboard players set #state dr 3
scoreboard players set #timer dr 1200
execute at @e[type=minecraft:marker,tag=dr.spot,limit=1] run function realms:drops/chests
# Built over in the last 10 minutes: one chest on top, into air only.
execute unless entity @e[type=minecraft:marker,tag=dr.chest] at @e[type=minecraft:marker,tag=dr.spot,limit=1] positioned over motion_blocking_no_leaves if block ~ ~ ~ #realms:drops/open run function realms:drops/place
execute unless entity @e[type=minecraft:marker,tag=dr.chest] run return run function realms:drops/blocked
execute at @e[type=minecraft:marker,tag=dr.spot,limit=1] positioned over motion_blocking_no_leaves run summon minecraft:text_display ~ ~1.8 ~ {Tags:["dr.label"],billboard:"center",text:{text:"Supply drop",color:"gold",bold:true}}
bossbar set realms:drop color red
bossbar set realms:drop max 1200
tellraw @a ["",{"text":"Supply drop: ","color":"gold","bold":true},{"text":"it has landed at ","color":"yellow"},{"nbt":"spot.x","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"realms:drops","color":"aqua"},{"text":". The chests despawn in 20 minutes, with whatever is still in them.","color":"yellow"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1.2
