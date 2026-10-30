# As the killer of a wanted player, in the same death: claims for the player slain marked.
advancement revoke @s only monkey:wanted/kill
execute unless entity @a[tag=wt.victim] run return 0
tag @a[tag=wt.victim,limit=1] add wt.target
function monkey:wanted/claim
tag @a remove wt.target
tag @a remove wt.victim
