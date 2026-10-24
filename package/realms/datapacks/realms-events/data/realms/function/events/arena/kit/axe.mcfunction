# Run as the players in the arena: execute as @a[tag=ev.arena] run function realms:events/arena/kit/axe
execute unless entity @s[tag=ev.arena] run return run tellraw @s {"text":"Kits are only for players in the arena.","color":"red"}
clear @s
effect clear @s
effect give @s minecraft:instant_health 1 10 true
effect give @s minecraft:saturation 1 10 true
item replace entity @s armor.head with minecraft:iron_helmet
item replace entity @s armor.chest with minecraft:iron_chestplate
item replace entity @s armor.legs with minecraft:iron_leggings
item replace entity @s armor.feet with minecraft:iron_boots
give @s minecraft:iron_axe 1
give @s minecraft:shield 1
give @s minecraft:cooked_beef 8
give @s minecraft:golden_apple 2
tellraw @s {"text":"Kit: axe.","color":"green"}
