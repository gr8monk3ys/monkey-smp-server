execute store result storage monkey:outposts tmp.h int 1 run scoreboard players get #o4 op.hold
function monkey:outposts/o/4/credit with storage monkey:outposts tmp
# The holder's name as the board run last wrote it (a renamed party shows its new name).
function monkey:outposts/o/4/label
execute as @e[type=minecraft:text_display,tag=op.l4] run data modify entity @s text set from storage monkey:outposts label.o4
