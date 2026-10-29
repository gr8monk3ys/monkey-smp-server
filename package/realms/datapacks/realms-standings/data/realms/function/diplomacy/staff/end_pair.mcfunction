$execute unless score #$(lo).$(hi) dp.war matches 1.. unless score #$(lo).$(hi) dp.pact matches 1 run return run tellraw @s {"text":"Those two have no war or pact.","color":"red"}
function realms:diplomacy/end_pair with storage realms:diplomacy pair
$tellraw @a ["",{"text":"Staff ended the war or pact between ","color":"gold"},{"nbt":"names.f$(a)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" and ","color":"gold"},{"nbt":"names.f$(b)","storage":"realms:factions","interpret":true,"color":"white"},{"text":".","color":"gold"}]
$function realms:diplomacy/log {kind:"end",a:$(a),b:$(b)}
