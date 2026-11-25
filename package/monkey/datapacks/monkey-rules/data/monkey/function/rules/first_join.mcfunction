# Runs as a player the server hasn't seen before.
tag @s add monkey.joined
# Someone who played here before this pack tagged anyone gets neither the welcome nor the kit.
execute if predicate monkey:rules/returning run return 0
scoreboard players set @s monkey.welcome 3
function monkey:catchup/first_join
