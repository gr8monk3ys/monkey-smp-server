schedule function realms:outposts/second 20t replace
scoreboard players enable @a outposts
# A label left from an earlier spot goes once its chunk is loaded.
execute as @e[type=minecraft:text_display,tag=op.l1] unless score @s op.id = #o1 op.id run kill @s
execute as @e[type=minecraft:text_display,tag=op.l2] unless score @s op.id = #o2 op.id run kill @s
execute as @e[type=minecraft:text_display,tag=op.l3] unless score @s op.id = #o3 op.id run kill @s
execute as @e[type=minecraft:text_display,tag=op.l4] unless score @s op.id = #o4 op.id run kill @s
execute unless score #launched rw.day matches 1 run return 0
execute unless score #launched op matches 1 run function realms:outposts/launch
execute if score #season_locked ev.state matches 1 run return 0
execute unless score #auto op matches 1 run return 0
execute if data storage realms:outposts at.o1 run function realms:outposts/o/1/second with storage realms:outposts at.o1
execute if data storage realms:outposts at.o2 run function realms:outposts/o/2/second with storage realms:outposts at.o2
execute if data storage realms:outposts at.o3 run function realms:outposts/o/3/second with storage realms:outposts at.o3
execute if data storage realms:outposts at.o4 run function realms:outposts/o/4/second with storage realms:outposts at.o4
scoreboard players add #sec op 1
execute if score #sec op matches 60.. run function realms:outposts/minute
