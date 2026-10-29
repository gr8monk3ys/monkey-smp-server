# Macro pair {a, b, lo, hi}: ends their war and pact (staff/end_pair, dissolve_pair); both get the pact back.
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(a) dp.pacts 1
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(b) dp.pacts 1
$scoreboard players reset #$(lo).$(hi) dp.war
$scoreboard players reset #$(lo).$(hi) dp.pact
