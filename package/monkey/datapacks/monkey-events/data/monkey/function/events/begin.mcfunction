# Macro {name:"Faction Raid"}: starts a new event, so everyone can be counted once for it.
scoreboard players add #event ev.state 1
$tellraw @a {"text":"Event: $(name)","color":"gold"}
