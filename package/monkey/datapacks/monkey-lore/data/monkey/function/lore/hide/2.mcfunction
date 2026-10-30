# Staff, in game, standing where it goes: hides week 2's page, "The First Loosening" (near the world border, before it moves).
# It shows and can be found from week 2. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w2"]}
tellraw @s [{"text":"Hid week 2's page \"The First Loosening\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w2,sort=nearest,limit=1]"}]
