# Staff: ends the drop now, whatever stage it is in; its chests go with what's in them.
execute unless score #state dr matches 1.. run return run tellraw @s {"text":"No supply drop is on.","color":"red"}
execute as @e[type=minecraft:marker,tag=dr.chest] at @s if block ~ ~ ~ minecraft:chest if data block ~ ~ ~ {CustomName:"Supply drop"} run setblock ~ ~ ~ minecraft:air
execute if score #state dr matches 2.. run tellraw @a ["",{"text":"","color":"gold","bold":true,"extra":[{"nbt":"name","storage":"realms:drops","interpret":true},": "]},{"text":"staff called it off.","color":"gray"}]
function realms:drops/cleanup
tellraw @s {"text":"Supply drop stopped.","color":"green"}
