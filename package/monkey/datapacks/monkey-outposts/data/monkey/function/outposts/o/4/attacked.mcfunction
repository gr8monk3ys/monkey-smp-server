# An attempt has started: the holder's members are told.
execute unless score #o4 op.hold matches 1.. run return 0
execute store result storage monkey:outposts tmp.h int 1 run scoreboard players get #o4 op.hold
execute store result storage monkey:outposts tmp.c int 1 run scoreboard players get #c op
function monkey:outposts/o/4/alert with storage monkey:outposts tmp
