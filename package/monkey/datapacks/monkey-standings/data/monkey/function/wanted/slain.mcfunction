# As a wanted player killed by a player (it fires before the killer's): marks them for the killer's claim,
# unless the board is off, the season hasn't launched or they died in the arena.
advancement revoke @s only monkey:wanted/slain
execute unless score #on wt matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
execute if entity @s[tag=ev.arena] run return 0
tag @s add wt.victim
