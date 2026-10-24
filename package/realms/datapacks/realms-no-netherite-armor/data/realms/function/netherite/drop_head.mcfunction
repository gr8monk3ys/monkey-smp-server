summon minecraft:item ~ ~ ~ {Item:{id:"minecraft:stone"},PickupDelay:40,Tags:["realms.netherite"]}
item replace entity @n[type=minecraft:item,tag=realms.netherite] contents from entity @s armor.head
tag @n[type=minecraft:item,tag=realms.netherite] remove realms.netherite
item replace entity @s armor.head with minecraft:air
