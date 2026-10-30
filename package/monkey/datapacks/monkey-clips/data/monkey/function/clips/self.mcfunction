# As the moment's player: their name (through a player head on an item display, as Server Firsts read
# it), then added with their faction. Where no chunk is loaded the name can't be read and is left out.
summon minecraft:item_display ~ ~ ~ {Tags:["cl.name"]}
loot replace entity @n[type=minecraft:item_display,tag=cl.name] contents loot monkey:clips/head
data modify storage monkey:clips m.name set from entity @n[type=minecraft:item_display,tag=cl.name] item.components."minecraft:profile".name
kill @e[type=minecraft:item_display,tag=cl.name]
execute unless data storage monkey:clips m{name:""} run function monkey:clips/add with storage monkey:clips m
