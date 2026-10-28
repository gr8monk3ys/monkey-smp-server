# From storage cand (found dry land): outpost 1 stands there now.
scoreboard players set #moved op 0
execute if data storage realms:outposts at.o1 run scoreboard players set #moved op 1
data modify storage realms:outposts at.o1 set from storage realms:outposts cand
data modify storage realms:outposts at.o1.name set value "North"
scoreboard players add #next op.id 1
scoreboard players operation #o1 op.id = #next op.id
scoreboard players set #d1 op 1
scoreboard players set #o1 op.prog 0
scoreboard players reset #o1 op.by
function realms:outposts/o/1/label
# The chunk is force-loaded while it is checked: put the label up now.
function realms:outposts/o/1/near with storage realms:outposts at.o1
execute if score #moved op matches 1 run function realms:outposts/moved with storage realms:outposts at.o1
execute if score #moved op matches 0 run function realms:outposts/placed with storage realms:outposts at.o1
