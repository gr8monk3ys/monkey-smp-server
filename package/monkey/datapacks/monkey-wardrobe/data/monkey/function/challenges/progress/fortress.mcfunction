# Defeat 15 fortress mobs: this week's progress into rc.faction, run as each player once a second while it is on.
scoreboard players set @s rc.faction 0
scoreboard players operation @s rc.faction += @s rc.fortress.0
execute if score @s rc.faction matches 15.. unless score @s rc.fortress.done matches 1 run function monkey:challenges/done/fortress
