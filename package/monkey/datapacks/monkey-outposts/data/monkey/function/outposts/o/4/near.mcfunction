# Macro at.o4, while a player is within 64 blocks: its chunk is loaded, so its label is too.
# Who is inside has visited an outpost (the first-week quest, tools/quest.py).
$scoreboard players set @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24] op.visit 1
# A label from an earlier spot goes first, so the one kept below is never it.
execute as @e[type=minecraft:text_display,tag=op.l4] unless score @s op.id = #o4 op.id run kill @s
$execute unless entity @e[type=minecraft:text_display,tag=op.l4,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24] positioned $(x) $(ly) $(z) align xz run summon minecraft:text_display ~0.5 ~ ~0.5 {Tags:["op.label","op.l4","op.new"],billboard:"center",view_range:2.0f}
scoreboard players operation @e[type=minecraft:text_display,tag=op.new] op.id = #o4 op.id
execute as @e[type=minecraft:text_display,tag=op.new] run data modify entity @s text set from storage monkey:outposts label.o4
tag @e[type=minecraft:text_display,tag=op.new] remove op.new
# Entities load after their chunk: one summoned before the old one loaded is one too many. Keep one.
execute store result score #lc op if entity @e[type=minecraft:text_display,tag=op.l4]
execute if score #lc op matches 2.. run function monkey:outposts/o/4/one_label
# Its square's corners, and a column at its middle while someone holds it.
$execute positioned $(zx) 0 $(zz) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(ex) 0 $(zz) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(zx) 0 $(ez) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute positioned $(ex) 0 $(ez) positioned over motion_blocking_no_leaves run particle minecraft:end_rod ~ ~0.5 ~ 0 1 0 0 3
$execute if score #o4 op.hold matches 1.. positioned $(x) $(ly) $(z) align xz run particle minecraft:end_rod ~0.5 ~ ~0.5 0.1 2 0.1 0.01 6
