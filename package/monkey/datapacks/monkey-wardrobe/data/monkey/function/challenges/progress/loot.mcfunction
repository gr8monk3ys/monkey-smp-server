# Open 8 loot chests: this week's progress into rc.explore, run as each player once a second while it is on.
scoreboard players set @s rc.explore 0
scoreboard players operation @s rc.explore += @s rc.loot.0
execute if score @s rc.explore matches 8.. unless score @s rc.loot.done matches 1 run function monkey:challenges/done/loot
