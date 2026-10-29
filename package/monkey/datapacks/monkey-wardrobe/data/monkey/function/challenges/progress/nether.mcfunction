# Visit a fortress and a bastion: this week's progress into rc.explore, run as each player once a second while it is on.
scoreboard players set @s rc.explore 0
scoreboard players operation @s rc.explore += @s rc.nether.fortress
scoreboard players operation @s rc.explore += @s rc.nether.bastion
execute if score @s rc.explore matches 2.. unless score @s rc.nether.done matches 1 run function monkey:challenges/done/nether
