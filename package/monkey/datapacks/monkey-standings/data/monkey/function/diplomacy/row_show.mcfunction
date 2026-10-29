# Macro pair {a, b, lo, hi}: the first that fits.
$execute if score #$(lo).$(hi) dp.war matches 1.. run return run function monkey:diplomacy/row/0 with storage monkey:diplomacy pair
$execute if score #$(lo).$(hi) dp.pact matches 1 run return run function monkey:diplomacy/row/1 with storage monkey:diplomacy pair
$execute if score #$(b).$(a) dp.offer matches 1.. run return run function monkey:diplomacy/row/2 with storage monkey:diplomacy pair
$execute if score #$(a).$(b) dp.offer matches 1.. run return run function monkey:diplomacy/row/3 with storage monkey:diplomacy pair
function monkey:diplomacy/row/4 with storage monkey:diplomacy pair
