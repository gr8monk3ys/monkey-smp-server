# Staff, in game, standing where it goes: hides week 3's page, "The Far Gate" (near the way to the End).
# It shows and can be found from week 3. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w3"]}
tellraw @s [{"text":"Hid week 3's page \"The Far Gate\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w3,sort=nearest,limit=1]"}]
