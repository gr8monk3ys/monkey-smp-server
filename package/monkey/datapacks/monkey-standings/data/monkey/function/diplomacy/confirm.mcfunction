# Macro pair {a, b, lo, hi}: faction a's leader confirmed a 7-day war on faction b.
execute unless score #formal dp.state matches 1 run return run tellraw @s {"text":"Pick from the menu: /trigger diplomacy","color":"red"}
execute if function monkey:diplomacy/wars/refusals_now run return 0
$scoreboard players reset #$(a).$(b) dp.offer
$scoreboard players reset #$(b).$(a) dp.offer
$tellraw @a ["",{"text":"War! ","color":"red","bold":true},{"nbt":"names.f$(a)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" (","color":"gray"},{"selector":"@s","color":"gray"},{"text":")","color":"gray"},{"text":" declared war on ","color":"red"},{"nbt":"names.f$(b)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":". It lasts 7 days: the faction with more kills of the other wins. Kills between them count double in the weekly standings. /trigger diplomacy shows the score.","color":"gray"}]
execute if score #on sg matches 1 run tellraw @a {"text":"Siege windows open every faction's claims to raids: /trigger sieges says when.","color":"gray"}
execute unless score #on sg matches 1 run tellraw @a {"text":"Claims still protect, and the griefing rules still apply.","color":"gray"}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1
$function monkey:diplomacy/log {kind:"declare",a:$(a),b:$(b)}
$scoreboard players operation #$(lo).$(hi) dp.war = #seq dp.state
$scoreboard players operation #$(lo).$(hi) dp.until = #now sg
$scoreboard players add #$(lo).$(hi) dp.until 10080
$scoreboard players set #$(a).$(b) dp.score 0
$scoreboard players set #$(b).$(a) dp.score 0
$scoreboard players operation #f$(a) dp.next = #now sg
$scoreboard players add #f$(a) dp.next 2880
$data modify storage monkey:diplomacy wars append value {lo:$(lo),hi:$(hi)}
$execute store result score #f$(a) dp.last run time query gametime
