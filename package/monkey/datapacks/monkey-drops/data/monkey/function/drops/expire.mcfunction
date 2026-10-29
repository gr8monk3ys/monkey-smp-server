# The chests go with what's left in them (setblock clears a container it replaces: nothing drops).
execute as @e[type=minecraft:marker,tag=dr.chest] at @s if block ~ ~ ~ minecraft:chest if data block ~ ~ ~ {CustomName:"Supply drop"} run setblock ~ ~ ~ minecraft:air
tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"monkey:drops","interpret":true},": "]},{"text":"the chests at ","color":"yellow"},{"nbt":"spot.x","storage":"monkey:drops","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"spot.z","storage":"monkey:drops","color":"aqua"},{"text":" have despawned.","color":"yellow"}]
function monkey:drops/cleanup
