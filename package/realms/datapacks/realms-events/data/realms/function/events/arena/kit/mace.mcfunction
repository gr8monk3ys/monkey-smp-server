# Run as the players in the arena: execute as @a[tag=ev.arena] run function realms:events/arena/kit/mace
execute unless entity @s[tag=ev.arena] run return run tellraw @s {"text":"Kits are only for players in the arena.","color":"red"}
clear @s
effect clear @s
effect give @s minecraft:instant_health 1 10 true
effect give @s minecraft:saturation 1 10 true
item replace entity @s armor.head with minecraft:iron_helmet
item replace entity @s armor.chest with minecraft:iron_chestplate
item replace entity @s armor.legs with minecraft:iron_leggings
item replace entity @s armor.feet with minecraft:iron_boots
give @s minecraft:mace 1
give @s minecraft:wind_charge 8
give @s minecraft:stone_sword 1
give @s minecraft:cooked_beef 8
give @s minecraft:golden_apple 2
tellraw @s {"text":"Kit: mace.","color":"green"}
