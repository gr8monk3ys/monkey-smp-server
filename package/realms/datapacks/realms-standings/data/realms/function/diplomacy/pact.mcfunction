# Macro pair {a, b, lo, hi}: faction a offers faction b a pact, or accepts b's offer.
$execute if score #$(lo).$(hi) dp.pact matches 1 run return run tellraw @s {"text":"You have a pact with them already.","color":"red"}
$execute if score #f$(a) dp.pacts matches 2.. run return run tellraw @s {"text":"Your faction has 2 pacts, the most it can hold (rule 31: alliances, not confederations). Break one first.","color":"red"}
$execute if score #f$(b) dp.pacts matches 2.. run return run tellraw @s {"text":"They have 2 pacts, the most a faction can hold.","color":"red"}
$execute if score #$(b).$(a) dp.offer matches 1 run return run function realms:diplomacy/accept with storage realms:diplomacy pair
$execute if score #$(a).$(b) dp.offer matches 1 run return run tellraw @s {"text":"Your offer stands until they accept it, or until Sunday's close.","color":"red"}
$scoreboard players set #$(a).$(b) dp.offer 1
$tellraw @a ["",{"nbt":"names.f$(a)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" (","color":"gray"},{"selector":"@s","color":"gray"},{"text":")","color":"gray"},{"text":" offers ","color":"aqua"},{"nbt":"names.f$(b)","storage":"realms:factions","interpret":true,"color":"white"},{"text":" a pact.","color":"aqua"},{"text":" Their leader can accept it with /trigger diplomacy until Sunday's close.","color":"gray"}]
$function realms:diplomacy/log {kind:"offer",a:$(a),b:$(b)}
$execute store result score #f$(a) dp.last run time query gametime
