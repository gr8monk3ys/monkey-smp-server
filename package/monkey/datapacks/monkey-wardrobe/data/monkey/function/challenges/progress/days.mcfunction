# Play on 3 different days: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players operation @s rc.solo = @s rc.days
execute if score @s rc.solo matches 3.. unless score @s rc.days.done matches 1 run function monkey:challenges/done/days
