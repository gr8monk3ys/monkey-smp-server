# A player with grace hurt a player (advancement monkey:rules/grace_attack). Fights in the event
# arena don't count.
advancement revoke @s only monkey:rules/grace_attack
execute unless entity @s[tag=ev.arena] run function monkey:rules/grace_end
