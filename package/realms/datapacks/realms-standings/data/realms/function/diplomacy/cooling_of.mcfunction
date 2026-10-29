# 1 when faction $(a) declared something in the last 120 seconds.
$execute unless score #f$(a) dp.last matches -2147483648.. run return 0
execute store result score #now dp.tmp run time query gametime
$scoreboard players operation #now dp.tmp -= #f$(a) dp.last
execute if score #now dp.tmp matches 0..2399 run return 1
return 0
