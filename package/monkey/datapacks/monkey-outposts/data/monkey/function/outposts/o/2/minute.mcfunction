execute store result storage monkey:outposts tmp.h int 1 run scoreboard players get #o2 op.hold
function monkey:outposts/o/2/credit with storage monkey:outposts tmp
# The holder's name as the board run last wrote it (a renamed party shows its new name).
function monkey:outposts/o/2/label
execute as @e[type=minecraft:text_display,tag=op.l2] run data modify entity @s text set from storage monkey:outposts label.o2
