# Defeat 2 piglin brutes: this week's progress into rc.faction, run as each player once a second while it is on.
scoreboard players set @s rc.faction 0
scoreboard players operation @s rc.faction += @s rc.brutes.0
execute if score @s rc.faction matches 2.. unless score @s rc.brutes.done matches 1 run function monkey:challenges/done/brutes
