# Staff, in game, standing where it goes: hides week 8's page, "What He Built" (by the Build Battle plots).
# It shows and can be found from week 8. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w8"]}
tellraw @s [{"text":"Hid week 8's page \"What He Built\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w8,sort=nearest,limit=1]"}]
