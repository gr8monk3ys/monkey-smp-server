scoreboard players add #t fn 1
scoreboard players set #left fn 6600
scoreboard players operation #left fn -= #t fn
execute store result bossbar monkey:finale value run scoreboard players get #left fn
execute if score #t fn matches 540 run tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"the border starts closing in 1 minute. Head for the monument at ","color":"gold"},{"nbt":"at.x","storage":"monkey:finale","color":"yellow"},{"text":", ","color":"yellow"},{"nbt":"at.z","storage":"monkey:finale","color":"yellow"},{"text":".","color":"gold"}]
execute if score #t fn matches 600 run function monkey:finale/shrink
execute if score #t fn matches 3000 run function monkey:finale/hold
execute if score #phase fn matches 2..3 run function monkey:finale/steer
execute if score #phase fn matches 3 run function monkey:finale/sample with storage monkey:finale at
execute if score #t fn matches 6000 run tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"10 minutes left. Hold the monument.","color":"gold"}]
execute if score #t fn matches 6540 run tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"1 minute left.","color":"gold"}]
execute if score #t fn matches 6600.. run function monkey:finale/close
