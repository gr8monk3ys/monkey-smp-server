# Win a raid: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function monkey:firsts/claim/raid
execute if score #raid rf matches 1.. run return 0
scoreboard players set #raid rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.raid = #claimed rf
function monkey:firsts/name
data modify storage monkey:firsts held.raid set value {name:"",order:0,week:-1}
data modify storage monkey:firsts held.raid.name set from storage monkey:firsts name
execute store result storage monkey:firsts held.raid.order int 1 run scoreboard players get #claimed rf
execute store result storage monkey:firsts held.raid.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"win a raid","color":"yellow","hover_event":{"action":"show_text","value":"Defend a village through a whole raid."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Win a raid","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
