# An attempt has started: the holder's members are told.
execute unless score #o3 op.hold matches 1.. run return 0
execute store result storage realms:outposts tmp.h int 1 run scoreboard players get #o3 op.hold
execute store result storage realms:outposts tmp.c int 1 run scoreboard players get #c op
function realms:outposts/o/3/alert with storage realms:outposts tmp
