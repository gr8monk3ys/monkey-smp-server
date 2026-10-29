# Breed 16 animals: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.breed.0
execute if score @s rc.solo matches 16.. unless score @s rc.breed.done matches 1 run function monkey:challenges/done/breed
