# The border's centre moves to the monument, a block a second each way: with the shrink, an edge moves
# at most about 2.2 blocks a second, under half walking pace.
execute if score #bx fn = #mx fn if score #bz fn = #mz fn run return 0
execute if score #bx fn < #mx fn run scoreboard players add #bx fn 1
execute if score #bx fn > #mx fn run scoreboard players remove #bx fn 1
execute if score #bz fn < #mz fn run scoreboard players add #bz fn 1
execute if score #bz fn > #mz fn run scoreboard players remove #bz fn 1
execute store result storage monkey:finale at.bx int 1 run scoreboard players get #bx fn
execute store result storage monkey:finale at.bz int 1 run scoreboard players get #bz fn
function monkey:finale/center with storage monkey:finale at
