# Mine 6 diamond ore: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.diamonds.0
scoreboard players operation @s rc.solo += @s rc.diamonds.1
scoreboard players operation @s rc.solo -= @s rc.diamonds.m0
scoreboard players operation @s rc.solo -= @s rc.diamonds.m1
execute if score @s rc.solo matches ..-1 run scoreboard players set @s rc.solo 0
execute if score @s rc.solo matches 6.. unless score @s rc.diamonds.done matches 1 run function monkey:challenges/done/diamonds
