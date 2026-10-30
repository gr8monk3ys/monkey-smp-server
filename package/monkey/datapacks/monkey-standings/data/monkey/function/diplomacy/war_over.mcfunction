# Macro {lo, hi, seq}: the Sunday close ends the war declared as number seq, if it still runs.
$execute unless score #$(lo).$(hi) dp.war matches $(seq) run return 0
$execute if score #$(lo).$(hi) dp.until matches -2147483648.. run return 0
$scoreboard players reset #$(lo).$(hi) dp.war
scoreboard players add #ended dp.state 1
