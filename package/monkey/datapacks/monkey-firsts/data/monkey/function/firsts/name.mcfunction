# Puts this player's name in storage monkey:firsts name ("" if it can't), through a player head of them
# on an item display that exists only for this function.
data modify storage monkey:firsts name set value ""
summon minecraft:item_display ~ ~ ~ {Tags:["rf.name"]}
loot replace entity @n[type=minecraft:item_display,tag=rf.name] contents loot monkey:firsts/head
data modify storage monkey:firsts name set from entity @n[type=minecraft:item_display,tag=rf.name] item.components."minecraft:profile".name
kill @e[type=minecraft:item_display,tag=rf.name]
