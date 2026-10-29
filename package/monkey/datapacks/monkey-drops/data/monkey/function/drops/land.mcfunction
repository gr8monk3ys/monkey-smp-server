scoreboard players set #state dr 3
scoreboard players set #timer dr 1200
execute at @e[type=minecraft:marker,tag=dr.spot,limit=1] run function monkey:drops/chests
# Built over in the last 10 minutes: one chest on top, into air only.
execute unless entity @e[type=minecraft:marker,tag=dr.chest] at @e[type=minecraft:marker,tag=dr.spot,limit=1] positioned over motion_blocking_no_leaves if block ~ ~ ~ #monkey:drops/open run function monkey:drops/place
execute unless entity @e[type=minecraft:marker,tag=dr.chest] run return run function monkey:drops/blocked
execute unless score #meteor dr matches 1 at @e[type=minecraft:marker,tag=dr.spot,limit=1] positioned over motion_blocking_no_leaves run summon minecraft:text_display ~ ~1.8 ~ {Tags:["dr.label"],billboard:"center",text:{text:"Supply drop",color:"gold",bold:true}}
execute if score #meteor dr matches 1 at @e[type=minecraft:marker,tag=dr.spot,limit=1] run function monkey:drops/impact
bossbar set monkey:drop color red
bossbar set monkey:drop max 1200
tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"monkey:drops","interpret":true},": "]},{"text":"it has landed at ","color":"yellow"},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"monkey:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":". The chests despawn in 20 minutes, with whatever is still in them.","color":"yellow"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1.2
