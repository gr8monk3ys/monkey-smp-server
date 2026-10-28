# From storage cand (found dry land): outpost 3 stands there now.
scoreboard players set #moved op 0
execute if data storage realms:outposts at.o3 run scoreboard players set #moved op 1
data modify storage realms:outposts at.o3 set from storage realms:outposts cand
data modify storage realms:outposts at.o3.name set value "South"
scoreboard players add #next op.id 1
scoreboard players operation #o3 op.id = #next op.id
scoreboard players set #d3 op 1
scoreboard players set #o3 op.prog 0
scoreboard players reset #o3 op.by
function realms:outposts/o/3/label
# The chunk is force-loaded while it is checked: put the label up now.
function realms:outposts/o/3/near with storage realms:outposts at.o3
execute if score #moved op matches 1 run function realms:outposts/moved with storage realms:outposts at.o3
execute if score #moved op matches 0 run function realms:outposts/placed with storage realms:outposts at.o3
