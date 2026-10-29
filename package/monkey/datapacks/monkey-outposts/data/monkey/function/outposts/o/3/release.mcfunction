scoreboard players reset #o3 op.hold
scoreboard players reset #o3 op.by
scoreboard players set #o3 op.prog 0
function monkey:outposts/o/3/label
execute as @e[type=minecraft:text_display,tag=op.l3] run data modify entity @s text set from storage monkey:outposts label.o3
