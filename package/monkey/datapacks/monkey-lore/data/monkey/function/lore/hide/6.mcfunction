# Staff, in game, standing where it goes: hides week 6's page, "The Long Night" (at spawn, under the Midwinter lights).
# It shows and can be found from week 6. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w6"]}
tellraw @s [{"text":"Hid week 6's page \"The Long Night\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w6,sort=nearest,limit=1]"}]
