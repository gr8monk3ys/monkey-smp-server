execute store result storage monkey:outposts tmp.h int 1 run scoreboard players get #o1 op.hold
function monkey:outposts/o/1/credit with storage monkey:outposts tmp
# The holder's name as the board run last wrote it (a renamed party shows its new name).
function monkey:outposts/o/1/label
execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text set from storage monkey:outposts label.o1
