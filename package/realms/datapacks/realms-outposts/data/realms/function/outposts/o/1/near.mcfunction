# Macro at.o1, while a player is within 64 blocks: its chunk is loaded, so its label is too.
$execute unless entity @e[type=minecraft:text_display,tag=op.l1,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24] run summon minecraft:text_display $(x).5 $(ly) $(z).5 {Tags:["op.label","op.l1","op.new"],billboard:"center",view_range:2.0f,text:{text:""}}
scoreboard players operation @e[type=minecraft:text_display,tag=op.new] op.id = #o1 op.id
tag @e[type=minecraft:text_display,tag=op.new] remove op.new
# Entities load after their chunk: a label summoned before the old one loaded is one too many.
execute store result score #lc op if entity @e[type=minecraft:text_display,tag=op.l1]
execute if score #lc op matches 2.. run kill @e[type=minecraft:text_display,tag=op.l1,limit=1]
execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text set from storage realms:outposts label.o1
# Its square's corners, and a column at its middle while someone holds it.
$execute positioned $(zx) 0 $(zz) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(ex) 0 $(zz) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(zx) 0 $(ez) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(ex) 0 $(ez) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute if score #o1 op.hold matches 1.. run particle minecraft:end_rod $(x).5 $(ly) $(z).5 0.1 2 0.1 0.01 6
