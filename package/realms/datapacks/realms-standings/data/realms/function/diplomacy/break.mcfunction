# Macro pair {a, b, lo, hi}: faction a breaks its pact with faction b.
$execute unless score #$(lo).$(hi) dp.pact matches 1 run return run tellraw @s {"text":"You have no pact with them.","color":"red"}
$scoreboard players reset #$(lo).$(hi) dp.pact
$scoreboard players remove #f$(a) dp.pacts 1
$scoreboard players remove #f$(b) dp.pacts 1
$tellraw @a ["",{"text":"Pact broken: ","color":"dark_red","bold":true},{"nbt":"names.f$(a)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" (","color":"gray"},{"selector":"@s","color":"gray"},{"text":")","color":"gray"},{"text":" broke its pact with ","color":"dark_red"},{"nbt":"names.f$(b)","storage":"realms:factions","interpret":true,"color":"white"},{"text":".","color":"gray"}]
execute as @a at @s run playsound minecraft:block.anvil.land master @s ~ ~ ~ 0.4 0.8
$function realms:diplomacy/log {kind:"break",a:$(a),b:$(b)}
$execute store result score #f$(a) dp.last run time query gametime
