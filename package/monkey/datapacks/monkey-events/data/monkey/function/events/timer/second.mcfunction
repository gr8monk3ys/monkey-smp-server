scoreboard players remove #timer ev.timer 1
execute store result bossbar monkey:timer value run scoreboard players get #timer ev.timer
scoreboard players operation #timer_min ev.timer = #timer ev.timer
scoreboard players add #timer_min ev.timer 59
scoreboard players operation #timer_min ev.timer /= #60 ev.timer
bossbar set monkey:timer players @a
bossbar set monkey:timer name [{"storage":"monkey:events","nbt":"timer.name","color":"aqua"},{"text":": ","color":"aqua"},{"score":{"name":"#timer_min","objective":"ev.timer"},"color":"white"},{"text":" min left","color":"aqua"}]
execute if score #timer ev.timer matches 600 run tellraw @a [{"storage":"monkey:events","nbt":"timer.name","color":"aqua"},{"text":": 10 minutes left.","color":"aqua"}]
execute if score #timer ev.timer matches 300 run tellraw @a [{"storage":"monkey:events","nbt":"timer.name","color":"aqua"},{"text":": 5 minutes left.","color":"aqua"}]
execute if score #timer ev.timer matches 60 run tellraw @a [{"storage":"monkey:events","nbt":"timer.name","color":"aqua"},{"text":": 1 minute left.","color":"aqua"}]
execute if score #timer ev.timer matches ..0 run return run function monkey:events/timer/over
