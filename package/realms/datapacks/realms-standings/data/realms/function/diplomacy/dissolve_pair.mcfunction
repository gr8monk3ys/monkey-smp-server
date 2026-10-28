$execute unless score #$(lo).$(hi) dp.war matches 1 unless score #$(lo).$(hi) dp.pact matches 1 run return 0
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(a) dp.pacts 1
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(b) dp.pacts 1
$scoreboard players reset #$(lo).$(hi) dp.war
$scoreboard players reset #$(lo).$(hi) dp.pact
$tellraw @a ["",{"text":"The war or pact between ","color":"gray"},{"nbt":"names.f$(a)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" and ","color":"gray"},{"nbt":"names.f$(b)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" is over: one of them is no longer a faction.","color":"gray"}]
