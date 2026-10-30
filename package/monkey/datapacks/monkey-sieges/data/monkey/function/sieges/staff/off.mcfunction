scoreboard players set #on sg 0
execute if score #open sg matches 1 run function monkey:sieges/close
tellraw @s ["",{"text":"Outpost sieges are off.","color":"gold"}]
