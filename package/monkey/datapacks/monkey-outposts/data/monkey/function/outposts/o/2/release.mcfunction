scoreboard players reset #o2 op.hold
scoreboard players reset #o2 op.by
scoreboard players set #o2 op.prog 0
function monkey:outposts/o/2/label
execute as @e[type=minecraft:text_display,tag=op.l2] run data modify entity @s text set from storage monkey:outposts label.o2
