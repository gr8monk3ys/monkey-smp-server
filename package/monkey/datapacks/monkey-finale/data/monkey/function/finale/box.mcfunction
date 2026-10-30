# Macro {name}: the square #a blocks either way of the border's centre, as a corner and a width, into edge.
scoreboard players operation #b fn = #bx fn
scoreboard players operation #b fn -= #a fn
$execute store result storage monkey:finale edge.$(name)x int 1 run scoreboard players get #b fn
scoreboard players operation #b fn = #bz fn
scoreboard players operation #b fn -= #a fn
$execute store result storage monkey:finale edge.$(name)z int 1 run scoreboard players get #b fn
scoreboard players operation #b fn = #a fn
scoreboard players operation #b fn += #a fn
$execute store result storage monkey:finale edge.$(name)d int 1 run scoreboard players get #b fn
