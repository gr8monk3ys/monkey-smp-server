# Macro {a, b, seq}: the Sunday close ends the pact offer made as number seq, if it still stands.
$execute unless score #$(a).$(b) dp.offer matches $(seq) run return 0
$scoreboard players reset #$(a).$(b) dp.offer
