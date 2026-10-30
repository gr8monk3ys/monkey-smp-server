$execute unless score #f$(n) fn matches 1.. run return 0
$execute if score #f$(n) fn = #best fn run return run scoreboard players set #tie fn 1
$execute unless score #f$(n) fn > #best fn run return 0
$scoreboard players operation #best fn = #f$(n) fn
$scoreboard players set #win fn $(n)
scoreboard players set #tie fn 0
