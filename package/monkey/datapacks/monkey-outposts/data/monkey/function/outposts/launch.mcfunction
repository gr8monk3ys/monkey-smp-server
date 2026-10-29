# Once, the first second after the launch (monkey:rules/launch sets #launched rw.day): nothing from test
# play counts. The outposts go, and the timer places them anew within the hour.
# Labels lose their ids too, so any left from test play go when their chunk loads. A new epoch tells
# tools/standings.py that every minute from here on is new.
scoreboard players reset * op.hold
scoreboard players reset * op.by
scoreboard players reset * op.prog
scoreboard players reset * op.min
scoreboard players reset * op.id
execute store result score #epoch op run random value 1..1000000000
execute store result storage monkey:outposts epoch int 1 run scoreboard players get #epoch op
execute if score #busy op matches 1 run function monkey:outposts/unload with storage monkey:outposts cand
function monkey:outposts/done
data remove storage monkey:outposts at
data modify storage monkey:outposts log set value []
scoreboard players set #ring op 0
scoreboard players set #seq op 0
scoreboard players set #launched op 1
