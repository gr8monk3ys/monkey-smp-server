summon minecraft:item ~ ~ ~ {Item:{id:"minecraft:stone"},PickupDelay:40,Tags:["realms.netherite"]}
item replace entity @n[type=minecraft:item,tag=realms.netherite] contents from entity @s armor.legs
tag @n[type=minecraft:item,tag=realms.netherite] remove realms.netherite
item replace entity @s armor.legs with minecraft:air
