# Mine 4 ancient debris: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.debris.0
scoreboard players operation @s rc.solo -= @s rc.debris.m0
execute if score @s rc.solo matches ..-1 run scoreboard players set @s rc.solo 0
execute if score @s rc.solo matches 4.. unless score @s rc.debris.done matches 1 run function monkey:challenges/done/debris
