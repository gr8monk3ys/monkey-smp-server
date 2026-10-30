scoreboard players set #on sg 0
execute if score #open sg matches 1 run function monkey:sieges/close
execute if score #applied sg matches 1 run function monkey:sieges/lock
tellraw @s ["",{"text":"Siege windows are off: ","color":"gold"},{"text":"claims are protected all the time.","color":"gray"}]
