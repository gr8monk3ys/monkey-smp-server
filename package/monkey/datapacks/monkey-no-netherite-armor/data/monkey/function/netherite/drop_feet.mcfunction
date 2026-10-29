summon minecraft:item ~ ~ ~ {Item:{id:"minecraft:stone"},PickupDelay:40,Tags:["monkey.netherite"]}
item replace entity @n[type=minecraft:item,tag=monkey.netherite] contents from entity @s armor.feet
tag @n[type=minecraft:item,tag=monkey.netherite] remove monkey.netherite
item replace entity @s armor.feet with minecraft:air
