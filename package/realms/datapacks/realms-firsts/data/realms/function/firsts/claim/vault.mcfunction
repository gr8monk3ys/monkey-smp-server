# Open a trial vault: this player is the first. Staff can run it as a player to make good an outage (at
# them: the name is read where they stand): execute as NAME at @s run function realms:firsts/claim/vault
execute if score #vault rf matches 1.. run return 0
scoreboard players set #vault rf 1
scoreboard players add #claimed rf 1
scoreboard players operation @s rf.vault = #claimed rf
function realms:firsts/name
data modify storage realms:firsts held.vault set value {name:"",order:0,week:-1}
data modify storage realms:firsts held.vault.name set from storage realms:firsts name
execute store result storage realms:firsts held.vault.order int 1 run scoreboard players get #claimed rf
execute store result storage realms:firsts held.vault.week int 1 run scoreboard players get #week rc.week
tellraw @a ["",{"text":"Server First! ","color":"gold","bold":true},{"selector":"@s","color":"yellow"},{"text":" is the first on the server to ","color":"gold"},{"text":"open a trial vault","color":"yellow","hover_event":{"action":"show_text","value":"Use a trial key (or an ominous one) on a vault in trial chambers."}},{"text":". ","color":"gold"},{"text":"[All firsts]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger firsts"}}]
title @a subtitle ["",{"selector":"@s","color":"yellow"},{"text":": Open a trial vault","color":"white"}]
title @a title {"text":"Server First","color":"gold","bold":true}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1
