# Takes the next spot, loads the chunks around it and checks the ground in a second.
scoreboard players set #state dr 1
scoreboard players set #wait dr 0
data modify storage monkey:drops spot set from storage monkey:drops spots[0]
data remove storage monkey:drops spots[0]
execute store result score #x dr run data get storage monkey:drops spot.x
execute store result score #z dr run data get storage monkey:drops spot.z
execute store result storage monkey:drops spot.x0 int 1 run scoreboard players remove #x dr 4
execute store result storage monkey:drops spot.z0 int 1 run scoreboard players remove #z dr 4
execute store result storage monkey:drops spot.x1 int 1 run scoreboard players add #x dr 8
execute store result storage monkey:drops spot.z1 int 1 run scoreboard players add #z dr 8
function monkey:drops/hold with storage monkey:drops spot
schedule function monkey:drops/check 20t replace
