# Mine 48 iron ore: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.iron.0
scoreboard players operation @s rc.solo += @s rc.iron.1
scoreboard players operation @s rc.solo -= @s rc.iron.m0
scoreboard players operation @s rc.solo -= @s rc.iron.m1
execute if score @s rc.solo matches ..-1 run scoreboard players set @s rc.solo 0
execute if score @s rc.solo matches 48.. unless score @s rc.iron.done matches 1 run function realms:challenges/done/iron
