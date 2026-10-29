# Make 20 villager trades: this week's progress into rc.solo, run as each player once a second while it is on.
scoreboard players set @s rc.solo 0
scoreboard players operation @s rc.solo += @s rc.trade.0
execute if score @s rc.solo matches 20.. unless score @s rc.trade.done matches 1 run function monkey:challenges/done/trade
