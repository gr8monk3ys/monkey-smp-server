# Enter the End: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function realms:firsts/claim/end
execute if score #end rf matches 1.. run return 0
scoreboard players set #end rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.end = #claimed rf
function realms:firsts/name
data modify storage realms:firsts held.end set value {name:"",order:0,week:-1}
data modify storage realms:firsts held.end.name set from storage realms:firsts name
execute store result storage realms:firsts held.end.order int 1 run scoreboard players get #claimed rf
execute store result storage realms:firsts held.end.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"enter the End","color":"yellow","hover_event":{"action":"show_text","value":"Go through an End portal once the End opens (Dragon Night)."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Enter the End","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
