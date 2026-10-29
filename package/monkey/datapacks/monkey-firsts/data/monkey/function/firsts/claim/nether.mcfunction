# Enter the Nether: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function monkey:firsts/claim/nether
execute if score #nether rf matches 1.. run return 0
scoreboard players set #nether rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.nether = #claimed rf
function monkey:firsts/name
data modify storage monkey:firsts held.nether set value {name:"",order:0,week:-1}
data modify storage monkey:firsts held.nether.name set from storage monkey:firsts name
execute store result storage monkey:firsts held.nether.order int 1 run scoreboard players get #claimed rf
execute store result storage monkey:firsts held.nether.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"enter the Nether","color":"yellow","hover_event":{"action":"show_text","value":"Go through a Nether portal (after the launch hour)."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Enter the Nether","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
