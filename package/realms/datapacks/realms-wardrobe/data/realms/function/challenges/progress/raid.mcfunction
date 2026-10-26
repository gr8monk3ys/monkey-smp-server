# Win a village raid: this week's progress into rc.faction, run as each player once a second while it is on.
scoreboard players set @s rc.faction 0
scoreboard players operation @s rc.faction += @s rc.raid.0
execute if score @s rc.faction matches 1.. unless score @s rc.raid.done matches 1 run function realms:challenges/done/raid
