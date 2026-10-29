scoreboard players reset #o4 op.hold
scoreboard players reset #o4 op.by
scoreboard players set #o4 op.prog 0
function realms:outposts/o/4/label
execute as @e[type=minecraft:text_display,tag=op.l4] run data modify entity @s text set from storage realms:outposts label.o4
