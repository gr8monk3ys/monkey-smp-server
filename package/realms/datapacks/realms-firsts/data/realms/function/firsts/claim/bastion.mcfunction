# Find a bastion: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function realms:firsts/claim/bastion
execute if score #bastion rf matches 1.. run return 0
scoreboard players set #bastion rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.bastion = #claimed rf
function realms:firsts/name
data modify storage realms:firsts held.bastion set value {name:"",order:0,week:-1}
data modify storage realms:firsts held.bastion.name set from storage realms:firsts name
execute store result storage realms:firsts held.bastion.order int 1 run scoreboard players get #claimed rf
execute store result storage realms:firsts held.bastion.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"find a bastion","color":"yellow","hover_event":{"action":"show_text","value":"Set foot in a bastion remnant."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Find a bastion","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
