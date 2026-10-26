# Defeat 6 breezes: this week's progress into rc.faction, run as each player once a second while it is on.
scoreboard players set @s rc.faction 0
scoreboard players operation @s rc.faction += @s rc.breezes.0
execute if score @s rc.faction matches 6.. unless score @s rc.breezes.done matches 1 run function realms:challenges/done/breezes
