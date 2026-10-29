# Visit 2 rare structures: this week's progress into rc.explore, run as each player once a second while it is on.
scoreboard players set @s rc.explore 0
scoreboard players operation @s rc.explore += @s rc.rare.trial_chambers
scoreboard players operation @s rc.explore += @s rc.rare.trail_ruins
scoreboard players operation @s rc.explore += @s rc.rare.ancient_city
scoreboard players operation @s rc.explore += @s rc.rare.mansion
execute if score @s rc.explore matches 2.. unless score @s rc.rare.done matches 1 run function monkey:challenges/done/rare
