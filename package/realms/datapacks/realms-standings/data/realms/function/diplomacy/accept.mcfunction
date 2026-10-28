# Macro pair {a, b, lo, hi}: faction a accepts faction b's offer. A war between them ends.
$scoreboard players reset #$(a).$(b) dp.offer
$scoreboard players reset #$(b).$(a) dp.offer
scoreboard players set #peace dp.tmp 0
$execute if score #$(lo).$(hi) dp.war matches 1 run scoreboard players set #peace dp.tmp 1
$scoreboard players reset #$(lo).$(hi) dp.war
$scoreboard players set #$(lo).$(hi) dp.pact 1
$scoreboard players add #f$(a) dp.pacts 1
$scoreboard players add #f$(b) dp.pacts 1
execute if score #peace dp.tmp matches 1 run function realms:diplomacy/peace with storage realms:diplomacy pair
execute unless score #peace dp.tmp matches 1 run function realms:diplomacy/pact_made with storage realms:diplomacy pair
$execute store result score #f$(a) dp.last run time query gametime
