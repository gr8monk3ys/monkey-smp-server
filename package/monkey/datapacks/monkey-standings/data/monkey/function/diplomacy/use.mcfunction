# Runs as a player who used /trigger diplomacy: 1 to 9 opens the menu, N*10 + action acts on faction N.
scoreboard players operation #v dp.tmp = @s diplomacy
scoreboard players set @s diplomacy 0
scoreboard players enable @s diplomacy
execute unless score #launched rw.day matches 1 run return run tellraw @s {"text":"War and pacts open at the launch.","color":"red"}
execute unless score @s st.faction matches 1.. run return run tellraw @s {"text":"You're in no faction the server knows yet. Make or join a party (/oparties); the server picks it up within the hour.","color":"red"}
execute if score #v dp.tmp matches ..9 run return run function monkey:diplomacy/menu
execute unless score @s st.leader matches 1 run return run tellraw @s {"text":"Only your faction's leader (its party owner) can declare war or make pacts.","color":"red"}
scoreboard players operation #act dp.tmp = #v dp.tmp
scoreboard players operation #act dp.tmp %= #10 dp.tmp
scoreboard players operation #b dp.tmp = #v dp.tmp
scoreboard players operation #b dp.tmp /= #10 dp.tmp
scoreboard players operation #a dp.tmp = @s st.faction
execute if score #a dp.tmp = #b dp.tmp run return run tellraw @s {"text":"That's your own faction.","color":"red"}
execute unless score #b dp.tmp matches 1..99 run return run tellraw @s {"text":"There's no such faction.","color":"red"}
function monkey:diplomacy/pair
execute unless function monkey:diplomacy/known run return run tellraw @s {"text":"There's no such faction (any more).","color":"red"}
execute if function monkey:diplomacy/cooling run return run tellraw @s {"text":"Your faction declared something in the last 2 minutes: wait a little.","color":"red"}
execute if score #act dp.tmp matches 1 run return run function monkey:diplomacy/war with storage monkey:diplomacy pair
execute if score #act dp.tmp matches 2 run return run function monkey:diplomacy/pact with storage monkey:diplomacy pair
execute if score #act dp.tmp matches 3 run return run function monkey:diplomacy/break with storage monkey:diplomacy pair
return run tellraw @s {"text":"Pick from the menu: /trigger diplomacy","color":"red"}
