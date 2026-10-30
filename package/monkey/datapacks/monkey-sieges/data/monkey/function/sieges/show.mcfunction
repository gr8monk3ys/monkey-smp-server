# Runs as a player who used /trigger sieges.
scoreboard players set @s sieges 0
scoreboard players enable @s sieges
execute unless score #on sg matches 1 run return run tellraw @s ["",{"text":"Siege windows are off: ","color":"gold"},{"text":"claims are protected all the time.","color":"gray"}]
execute if score #open sg matches 1 run scoreboard players operation #mins sg = #closes sg
execute unless score #open sg matches 1 run scoreboard players operation #mins sg = #opens sg
scoreboard players add #mins sg 59
scoreboard players operation #mins sg /= #60 sg
scoreboard players operation #hours sg = #mins sg
scoreboard players operation #hours sg /= #60 sg
scoreboard players operation #mins sg %= #60 sg
execute if score #open sg matches 1 run tellraw @s ["",{"text":"A siege window is open now","color":"red","bold":true},{"text":" (","color":"gray"},{"nbt":"label","storage":"monkey:sieges","color":"yellow"},{"text":"), ","color":"gray"},{"score":{"name":"#hours","objective":"sg"},"color":"yellow"},{"text":" h ","color":"gray"},{"score":{"name":"#mins","objective":"sg"},"color":"yellow"},{"text":" min left. Outside your own party, anyone can break blocks, open chests and doors, place blocks and set off TNT in any faction's claims. Spawn and the wilderness are as always, and so are animals, item frames and villagers in claims. The other rules still apply.","color":"gray"}]
execute unless score #open sg matches 1 unless score #synced sg matches 1 run return run tellraw @s ["",{"text":"Siege windows: ","color":"gold"},{"text":"the server is setting its clock; try again in a few minutes.","color":"gray"}]
execute unless score #open sg matches 1 run tellraw @s ["",{"text":"Next siege window: ","color":"gold"},{"nbt":"label","storage":"monkey:sieges","color":"yellow"},{"text":", in ","color":"gray"},{"score":{"name":"#hours","objective":"sg"},"color":"yellow"},{"text":" h ","color":"gray"},{"score":{"name":"#mins","objective":"sg"},"color":"yellow"},{"text":" min, for 2 hours. Outside your own party, anyone can break blocks, open chests and doors, place blocks and set off TNT in any faction's claims. Spawn and the wilderness are as always, and so are animals, item frames and villagers in claims. The other rules still apply.","color":"gray"}]
