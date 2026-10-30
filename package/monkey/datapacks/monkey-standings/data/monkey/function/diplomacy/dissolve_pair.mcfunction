$execute unless score #$(lo).$(hi) dp.war matches 1.. unless score #$(lo).$(hi) dp.pact matches 1 run return 0
data modify storage monkey:diplomacy pair.how set value "gone"
function monkey:diplomacy/end_pair with storage monkey:diplomacy pair
$tellraw @a ["",{"text":"The war or pact between ","color":"gray"},{"nbt":"names.f$(a)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" and ","color":"gray"},{"nbt":"names.f$(b)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" is over: one of them is no longer a faction.","color":"gray"}]
