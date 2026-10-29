scoreboard players reset #o1 op.hold
scoreboard players reset #o1 op.by
scoreboard players set #o1 op.prog 0
function monkey:outposts/o/1/label
execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text set from storage monkey:outposts label.o1
