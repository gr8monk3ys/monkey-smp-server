# Runs as a player the server hasn't seen before.
tag @s add realms.joined
# Someone who played here before this pack tagged anyone gets neither the welcome nor grace.
execute if predicate realms:rules/returning run return 0
scoreboard players set @s realms.welcome 3
# Rule 26: not in the launch hour, when the whole server starts together.
execute unless score #launching realms.rules matches 1 run function realms:rules/grace_start
