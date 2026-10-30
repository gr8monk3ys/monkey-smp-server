# Macro pair {a, b, lo, hi, how}: ends their war and pact (staff/end_pair, dissolve_pair); both get the pact
# back. A 7-day war's end is logged as `how` (staff or gone).
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(a) dp.pacts 1
$execute if score #$(lo).$(hi) dp.pact matches 1 run scoreboard players remove #f$(b) dp.pacts 1
$function monkey:diplomacy/wars/ended {lo:$(lo),hi:$(hi),how:"$(how)"}
$scoreboard players reset #$(lo).$(hi) dp.war
$scoreboard players reset #$(lo).$(hi) dp.pact
