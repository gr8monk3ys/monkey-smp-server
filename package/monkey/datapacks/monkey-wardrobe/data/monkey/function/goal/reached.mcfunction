# The target is reached: a celebration for everyone online, and fireworks over the board at spawn.
scoreboard players set #said rg 100
data modify storage monkey:goal status set value " reached"
tellraw @a ["",{"text":"Server goal reached! ","color":"gold","bold":true},{"nbt":"name","storage":"monkey:goal","color":"yellow"},{"text":"  ","color":"gray"},{"score":{"name":"#total","objective":"rg"},"color":"white"},{"text":"/","color":"gray"},{"score":{"name":"#target","objective":"rg"},"color":"white"},{"text":". Thank you, everyone. Fireworks at spawn.","color":"gray"}]
title @a subtitle {"nbt":"name","storage":"monkey:goal","color":"yellow"}
title @a title {"text":"Server goal reached","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
execute as @e[type=minecraft:text_display,tag=st.board] at @s run summon minecraft:firework_rocket ~ ~4 ~ {LifeTime:30,FireworksItem:{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":{flight_duration:2b,explosions:[{shape:"large_ball",colors:[I;16766720,16739125],fade_colors:[I;16777215],has_trail:1b,has_twinkle:1b}]}}}}
execute as @e[type=minecraft:text_display,tag=st.board] at @s run summon minecraft:firework_rocket ~2 ~4 ~ {LifeTime:36,FireworksItem:{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":{flight_duration:2b,explosions:[{shape:"large_ball",colors:[I;16766720,16739125],fade_colors:[I;16777215],has_trail:1b,has_twinkle:1b}]}}}}
execute as @e[type=minecraft:text_display,tag=st.board] at @s run summon minecraft:firework_rocket ~-2 ~4 ~ {LifeTime:42,FireworksItem:{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":{flight_duration:2b,explosions:[{shape:"large_ball",colors:[I;16766720,16739125],fade_colors:[I;16777215],has_trail:1b,has_twinkle:1b}]}}}}
