# As a player in the bubble: grace stays on (rule 26's item and attack check do the rest), and the hours
# count down only outside the arena.
execute unless score @s monkey.grace >= #keep ck run scoreboard players operation @s monkey.grace = #keep ck
execute if entity @s[tag=ev.arena] run return run title @s actionbar {"text":"Protection bubble: paused in the arena","color":"gray"}
scoreboard players remove @s ck.bubble 1
execute if score @s ck.bubble matches 28797 run function monkey:catchup/note
execute if score @s ck.bubble matches 0 run return run function monkey:catchup/over
scoreboard players operation @s ck.h = @s ck.bubble
scoreboard players operation @s ck.h /= #3600 ck
scoreboard players operation @s ck.m = @s ck.bubble
scoreboard players operation @s ck.m %= #3600 ck
scoreboard players operation @s ck.m /= #60 ck
title @s actionbar ["",{"text":"Protection bubble: ","color":"green"},{"score":{"name":"@s","objective":"ck.h"},"color":"white"},{"text":"h ","color":"gray"},{"score":{"name":"@s","objective":"ck.m"},"color":"white"},{"text":"m of play left. Attacking a player ends it.","color":"gray"}]
