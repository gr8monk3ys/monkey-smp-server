# Staff, in game: removes the hidden page nearest you (within 5 blocks).
execute unless entity @e[type=minecraft:marker,tag=lore.cache,distance=..5] run return run tellraw @s {"text":"No hidden page within 5 blocks.","color":"red"}
kill @e[type=minecraft:marker,tag=lore.cache,distance=..5,sort=nearest,limit=1]
tellraw @s {"text":"Removed the nearest hidden page.","color":"yellow"}
