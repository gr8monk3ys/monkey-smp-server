# Monkey SMP patch (charged_tick): a marker that a cube marked last tick keeps its button. The dropped-button
# cleanup still runs every tick, before that, as upstream's did.
execute at @s unless block ~ ~ ~ minecraft:mangrove_button run kill @e[type=item,nbt={Item:{count:1,id:"minecraft:mangrove_button"}},distance=..1,limit=1]
execute if entity @s[tag=sulfur_cube_charge_kept] run return run tag @s remove sulfur_cube_charge_kept
kill @s
fill ~ ~ ~ ~ ~ ~ minecraft:air replace minecraft:mangrove_button[powered=true,face=floor]
