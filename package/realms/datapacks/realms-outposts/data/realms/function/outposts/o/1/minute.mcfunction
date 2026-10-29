execute store result storage realms:outposts tmp.h int 1 run scoreboard players get #o1 op.hold
function realms:outposts/o/1/credit with storage realms:outposts tmp
# The holder's name as the board run last wrote it (a renamed party shows its new name).
function realms:outposts/o/1/label
execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text set from storage realms:outposts label.o1
