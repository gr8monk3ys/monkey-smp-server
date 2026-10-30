# Factions 1 to 99, one a call: the most points wins; the same most, a tie.
execute store result storage monkey:finale n.n int 1 run scoreboard players get #n fn
function monkey:finale/pick_one with storage monkey:finale n
scoreboard players add #n fn 1
execute if score #n fn matches ..99 run function monkey:finale/pick
