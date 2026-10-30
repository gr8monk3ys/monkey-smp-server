scoreboard players set #edge fn 0
execute in minecraft:overworld store result score #half fn run worldborder get
scoreboard players set #k fn 2
scoreboard players operation #half fn /= #k fn
# The warned box: EDGE_MARGIN inside the edge. The outside box: the border itself, a block over.
scoreboard players operation #a fn = #half fn
scoreboard players remove #a fn 16
execute if score #a fn matches ..24 run scoreboard players set #a fn 24
function monkey:finale/box {name:"warn"}
scoreboard players operation #a fn = #half fn
scoreboard players add #a fn 1
function monkey:finale/box {name:"out"}
scoreboard players operation #a fn = #half fn
scoreboard players remove #a fn 8
execute store result storage monkey:finale edge.r int 1 run scoreboard players get #a fn
data modify storage monkey:finale edge.x set from storage monkey:finale at.bx
data modify storage monkey:finale edge.z set from storage monkey:finale at.bz
function monkey:finale/edge_at with storage monkey:finale edge
