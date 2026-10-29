scoreboard players reset #o4 op.hold
scoreboard players reset #o4 op.by
scoreboard players set #o4 op.prog 0
function monkey:outposts/o/4/label
execute as @e[type=minecraft:text_display,tag=op.l4] run data modify entity @s text set from storage monkey:outposts label.o4
