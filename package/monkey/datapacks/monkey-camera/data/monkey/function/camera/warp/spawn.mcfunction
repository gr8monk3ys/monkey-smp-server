# The spawn point staff set with camera/set_spawn, from above.
execute unless data storage monkey:camera spawn.x run return run tellraw @s {"text":"Staff haven't set the camera's spawn point.","color":"red"}
function monkey:camera/to with storage monkey:camera spawn
function monkey:camera/anchor
