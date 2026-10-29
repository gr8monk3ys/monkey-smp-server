# Chop 128 logs: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.logs.0
scoreboard players operation @s rc.solo += @s rc.logs.1
scoreboard players operation @s rc.solo += @s rc.logs.2
scoreboard players operation @s rc.solo += @s rc.logs.3
scoreboard players operation @s rc.solo += @s rc.logs.4
scoreboard players operation @s rc.solo += @s rc.logs.5
scoreboard players operation @s rc.solo += @s rc.logs.6
scoreboard players operation @s rc.solo += @s rc.logs.7
scoreboard players operation @s rc.solo += @s rc.logs.8
scoreboard players operation @s rc.solo += @s rc.logs.9
scoreboard players operation @s rc.solo += @s rc.logs.10
scoreboard players operation @s rc.solo -= @s rc.logs.m0
scoreboard players operation @s rc.solo -= @s rc.logs.m1
scoreboard players operation @s rc.solo -= @s rc.logs.m2
scoreboard players operation @s rc.solo -= @s rc.logs.m3
scoreboard players operation @s rc.solo -= @s rc.logs.m4
scoreboard players operation @s rc.solo -= @s rc.logs.m5
scoreboard players operation @s rc.solo -= @s rc.logs.m6
scoreboard players operation @s rc.solo -= @s rc.logs.m7
scoreboard players operation @s rc.solo -= @s rc.logs.m8
scoreboard players operation @s rc.solo -= @s rc.logs.m9
scoreboard players operation @s rc.solo -= @s rc.logs.m10
execute if score @s rc.solo matches ..-1 run scoreboard players set @s rc.solo 0
execute if score @s rc.solo matches 128.. unless score @s rc.logs.done matches 1 run function monkey:challenges/done/logs
