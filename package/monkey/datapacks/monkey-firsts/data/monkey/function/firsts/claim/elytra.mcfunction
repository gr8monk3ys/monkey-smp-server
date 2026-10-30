# Find an elytra: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function monkey:firsts/claim/elytra
execute if score #elytra rf matches 1.. run return 0
scoreboard players set #elytra rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.elytra = #claimed rf
function monkey:firsts/name
data modify storage monkey:firsts held.elytra set value {name:"",order:0,week:-1}
data modify storage monkey:firsts held.elytra.name set from storage monkey:firsts name
execute store result storage monkey:firsts held.elytra.order int 1 run scoreboard players get #claimed rf
execute store result storage monkey:firsts held.elytra.week int 1 run scoreboard players get #week rc.week
# The name can't be read where no chunk is loaded (as the player changes dimension): second fills it in.
execute if data storage monkey:firsts held.elytra{name:""} run scoreboard players set #unnamed rf 1
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"find an elytra","color":"yellow","hover_event":{"action":"show_text","value":"Hold an elytra, from an End ship."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Find an elytra","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
