# Find a diamond: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function monkey:firsts/claim/diamond
execute if score #diamond rf matches 1.. run return 0
scoreboard players set #diamond rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.diamond = #claimed rf
function monkey:firsts/name
data modify storage monkey:firsts held.diamond set value {name:"",order:0,week:-1}
data modify storage monkey:firsts held.diamond.name set from storage monkey:firsts name
execute store result storage monkey:firsts held.diamond.order int 1 run scoreboard players get #claimed rf
execute store result storage monkey:firsts held.diamond.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"find a diamond","color":"yellow","hover_event":{"action":"show_text","value":"Hold a diamond: mined, looted or traded."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Find a diamond","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
