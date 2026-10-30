# Back to the leash's middle, in the Overworld, from above.
execute store result storage monkey:camera at.x int 1 run scoreboard players get @s cm.ax
execute store result storage monkey:camera at.z int 1 run scoreboard players get @s cm.az
function monkey:camera/to with storage monkey:camera at
title @s actionbar {"text":"The camera stays within 160 blocks of its warp, in the Overworld.","color":"gray"}
