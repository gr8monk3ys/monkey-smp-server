# Runs as a player the server hasn't seen before.
tag @s add monkey.joined
# Someone who played here before this pack tagged anyone gets neither the welcome nor grace.
execute if predicate monkey:rules/returning run return 0
scoreboard players set @s monkey.welcome 3
# Rule 26: not in the launch hour, when the whole server starts together.
execute unless score #launching monkey.rules matches 1 run function monkey:rules/grace_start
