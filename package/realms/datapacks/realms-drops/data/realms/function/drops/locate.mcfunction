# Takes the next spot, loads the chunks around it and checks the ground in a second.
scoreboard players set #state dr 1
scoreboard players set #wait dr 0
data modify storage realms:drops spot set from storage realms:drops spots[0]
data remove storage realms:drops spots[0]
execute store result score #x dr run data get storage realms:drops spot.x
execute store result score #z dr run data get storage realms:drops spot.z
execute store result storage realms:drops spot.x0 int 1 run scoreboard players remove #x dr 4
execute store result storage realms:drops spot.z0 int 1 run scoreboard players remove #z dr 4
execute store result storage realms:drops spot.x1 int 1 run scoreboard players add #x dr 8
execute store result storage realms:drops spot.z1 int 1 run scoreboard players add #z dr 8
function realms:drops/hold with storage realms:drops spot
schedule function realms:drops/check 20t replace
