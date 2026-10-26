# Staff: a drop where you stand.
execute store result storage realms:drops here.x int 1 run data get entity @s Pos[0]
execute store result storage realms:drops here.z int 1 run data get entity @s Pos[2]
function realms:drops/start with storage realms:drops here
