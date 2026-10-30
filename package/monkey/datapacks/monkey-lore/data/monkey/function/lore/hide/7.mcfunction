# Staff, in game, standing where it goes: hides week 7's page, "The Second Loosening" (near the world border, before it moves again).
# It shows and can be found from week 7. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w7"]}
tellraw @s [{"text":"Hid week 7's page \"The Second Loosening\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w7,sort=nearest,limit=1]"}]
