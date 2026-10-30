# 30 and 5 minutes before (or the first second after a restart inside them).
scoreboard players set #w1 sg 1
execute if score #opens sg matches ..300 run scoreboard players set #w2 sg 1
scoreboard players operation #mins sg = #opens sg
scoreboard players add #mins sg 59
scoreboard players operation #mins sg /= #60 sg
tellraw @a ["",{"text":"Siege window in ","color":"gold","bold":true},{"score":{"name":"#mins","objective":"sg"},"color":"yellow"},{"text":" min","color":"gold","bold":true},{"text":" (","color":"gray"},{"nbt":"label","storage":"monkey:sieges","color":"yellow"},{"text":"). Faction claims can be raided while it is open. /trigger sieges","color":"gray"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 0.8
