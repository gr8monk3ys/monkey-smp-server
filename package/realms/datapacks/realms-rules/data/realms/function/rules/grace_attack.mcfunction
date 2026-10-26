# A player with grace hurt a player (advancement realms:rules/grace_attack). Fights in the event
# arena don't count.
advancement revoke @s only realms:rules/grace_attack
execute unless entity @s[tag=ev.arena] run function realms:rules/grace_end
