scoreboard players remove #timer dr 1
scoreboard players operation #mins dr = #timer dr
scoreboard players add #mins dr 59
scoreboard players operation #mins dr /= #60 dr
execute store result bossbar realms:drop value run scoreboard players get #timer dr
bossbar set realms:drop players @a
bossbar set realms:drop name [{"text":"Supply drop at ","color":"yellow"},{"nbt":"spot.x","storage":"realms:drops","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"spot.z","storage":"realms:drops","color":"aqua"},{"text":": lands in ","color":"yellow"},{"score":{"name":"#mins","objective":"dr"},"color":"white"},{"text":" min","color":"yellow"}]
execute if score #timer dr matches 300 run tellraw @a ["",{"text":"Supply drop: ","color":"gold","bold":true},{"text":"5 minutes until it lands at ","color":"yellow"},{"nbt":"spot.x","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"realms:drops","color":"aqua"},{"text":".","color":"yellow"}]
execute if score #timer dr matches 60 run tellraw @a ["",{"text":"Supply drop: ","color":"gold","bold":true},{"text":"1 minute until it lands at ","color":"yellow"},{"nbt":"spot.x","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.y","storage":"realms:drops","color":"aqua"},{"text":" ","color":"aqua"},{"nbt":"spot.z","storage":"realms:drops","color":"aqua"},{"text":".","color":"yellow"}]
execute if score #timer dr matches ..0 run function realms:drops/land
