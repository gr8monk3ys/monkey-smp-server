scoreboard players operation #o2 op.hold = #c op
scoreboard players set #o2 op.prog 0
scoreboard players reset #o2 op.by
function realms:outposts/o/2/label
execute as @e[type=minecraft:text_display,tag=op.l2] run data modify entity @s text set from storage realms:outposts label.o2
execute store result storage realms:outposts tmp.c int 1 run scoreboard players get #c op
function realms:outposts/o/2/taken with storage realms:outposts tmp
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.4 1.4
