# From storage cand (found dry land): outpost 2 stands there now.
scoreboard players set #moved op 0
execute if data storage monkey:outposts at.o2 run scoreboard players set #moved op 1
data modify storage monkey:outposts at.o2 set from storage monkey:outposts cand
data modify storage monkey:outposts at.o2.name set value "East"
scoreboard players add #next op.id 1
scoreboard players operation #o2 op.id = #next op.id
scoreboard players set #d2 op 1
scoreboard players set #o2 op.prog 0
scoreboard players reset #o2 op.by
function monkey:outposts/o/2/label
# The chunk is force-loaded while it is checked: put the label up now.
function monkey:outposts/o/2/near with storage monkey:outposts at.o2
execute if score #moved op matches 1 run function monkey:outposts/moved with storage monkey:outposts at.o2
execute if score #moved op matches 0 run function monkey:outposts/placed with storage monkey:outposts at.o2
