$execute unless score #$(lo).$(hi) dp.war matches 1 unless score #$(lo).$(hi) dp.pact matches 1 run return run tellraw @s {"text":"Those two have no war or pact.","color":"red"}
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(a) dp.pacts 1
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(b) dp.pacts 1
$scoreboard players reset #$(lo).$(hi) dp.war
$scoreboard players reset #$(lo).$(hi) dp.pact
$tellraw @a ["",{"text":"Staff ended the war or pact between ","color":"gold"},{"nbt":"names.f$(a)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" and ","color":"gold"},{"nbt":"names.f$(b)","storage":"realms:factions","interpret":true,"color":"white"},{"text":".","color":"gold"}]
$function realms:diplomacy/log {kind:"end",a:$(a),b:$(b)}
