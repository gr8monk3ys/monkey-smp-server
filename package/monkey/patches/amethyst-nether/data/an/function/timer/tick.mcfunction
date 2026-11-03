## items
### bomb
execute as @e[tag=an.bomb_marker] unless predicate an:entity_properties/is_riding at @s run function an:items/bomb/make_explosion
execute as @e[type=minecraft:snowball,tag=!an.bomb_loaded,predicate=an:entity_properties/is_bomb] at @s run function an:items/bomb/add_marker
execute as @e[type=minecraft:item,tag=!an.bomb_loaded] if items entity @s contents minecraft:snowball[minecraft:custom_data~{an.bomb:true}] at @s run function an:items/bomb/add_marker
execute as @e[type=minecraft:item_frame,tag=!an.bomb_loaded] if items entity @s contents minecraft:snowball[minecraft:custom_data~{an.bomb:true}] at @s run function an:items/bomb/add_marker
execute as @e[type=minecraft:glow_item_frame,tag=!an.bomb_loaded] if items entity @s contents minecraft:snowball[minecraft:custom_data~{an.bomb:true}] at @s run function an:items/bomb/add_marker


## mechanics
### ender_pearl
execute as @e[type=minecraft:ender_pearl,predicate=an:location_check/biome/nether_roof] at @s run function an:mechanics/ender_pearl/no_above_roof