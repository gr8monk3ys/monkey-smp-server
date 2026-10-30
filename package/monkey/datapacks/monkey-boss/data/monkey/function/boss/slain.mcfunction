# The kill advancement's reward, as the player who landed the killing blow.
advancement revoke @s only monkey:boss/slain
execute unless score #state bs matches 2 run return 0
function monkey:firsts/name
data modify storage monkey:boss at.name set from storage monkey:firsts name
scoreboard players set #f bs 0
execute if score @s st.faction matches 1.. run scoreboard players operation #f bs = @s st.faction
execute store result storage monkey:boss at.faction int 1 run scoreboard players get #f bs
function monkey:boss/slain_record with storage monkey:boss at
execute if score #f bs matches 1.. run function monkey:boss/slain_faction with storage monkey:boss at
execute if score #f bs matches 0 run tellraw @a ["",{"selector":"@s","color":"yellow"},{"text":" slew The Edgewalker!","color":"gold","bold":true}]
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 0.8
function monkey:boss/end
