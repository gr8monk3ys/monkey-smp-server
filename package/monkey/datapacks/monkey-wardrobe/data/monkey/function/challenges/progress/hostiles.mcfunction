# Defeat 40 hostile mobs: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.hostiles.0
execute if score @s rc.solo matches 40.. unless score @s rc.hostiles.done matches 1 run function monkey:challenges/done/hostiles
