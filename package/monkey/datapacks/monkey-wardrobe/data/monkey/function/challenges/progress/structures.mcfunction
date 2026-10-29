# Visit 4 kinds of structure: this week's progress into rc.explore, run as each player once a second while it is on.
scoreboard players set @s rc.explore 0
scoreboard players operation @s rc.explore += @s rc.structures.village
scoreboard players operation @s rc.explore += @s rc.structures.outpost
scoreboard players operation @s rc.explore += @s rc.structures.ruined_portal
scoreboard players operation @s rc.explore += @s rc.structures.shipwreck
scoreboard players operation @s rc.explore += @s rc.structures.ocean_ruin
scoreboard players operation @s rc.explore += @s rc.structures.mineshaft
scoreboard players operation @s rc.explore += @s rc.structures.desert_pyramid
scoreboard players operation @s rc.explore += @s rc.structures.jungle_pyramid
scoreboard players operation @s rc.explore += @s rc.structures.swamp_hut
scoreboard players operation @s rc.explore += @s rc.structures.igloo
scoreboard players operation @s rc.explore += @s rc.structures.monument
execute if score @s rc.explore matches 4.. unless score @s rc.structures.done matches 1 run function monkey:challenges/done/structures
