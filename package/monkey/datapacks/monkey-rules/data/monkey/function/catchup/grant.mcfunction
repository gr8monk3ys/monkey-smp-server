# As the player. Staff can give it by hand: execute as NAME run function monkey:catchup/grant
execute if score @s ck.kit matches 1 run return 0
scoreboard players set @s ck.kit 1
give @s minecraft:iron_pickaxe 1
give @s minecraft:iron_axe 1
give @s minecraft:iron_shovel 1
give @s minecraft:iron_sword 1
give @s minecraft:cooked_beef 24
give @s minecraft:red_bed 1
give @s minecraft:torch 32
scoreboard players set @s ck.bubble 28800
scoreboard players enable @s end_grace
