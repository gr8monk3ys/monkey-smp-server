# Macro pair {a, b, lo, hi}: faction a declares war on faction b.
$execute if score #$(lo).$(hi) dp.pact matches 1 run return run tellraw @s {"text":"You have a pact with them. Break it first (everyone is told).","color":"red"}
$execute if score #$(lo).$(hi) dp.war matches 1.. run return run tellraw @s {"text":"You're at war with them already, until Sunday's close.","color":"red"}
$scoreboard players reset #$(a).$(b) dp.offer
$scoreboard players reset #$(b).$(a) dp.offer
$tellraw @a ["",{"text":"War! ","color":"red","bold":true},{"nbt":"names.f$(a)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" (","color":"gray"},{"selector":"@s","color":"gray"},{"text":")","color":"gray"},{"text":" declared war on ","color":"red"},{"nbt":"names.f$(b)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":". Kills between them count double in the weekly standings until Sunday's close. Claims still protect, and the griefing rules still apply.","color":"gray"}]
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1
$function monkey:diplomacy/log {kind:"war",a:$(a),b:$(b)}
$scoreboard players operation #$(lo).$(hi) dp.war = #seq dp.state
$execute store result score #f$(a) dp.last run time query gametime
