# Staff, in game, standing where it goes: hides week 10's page, "Where Ruk Went" (at one of the outposts).
# It shows and can be found from week 10. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w10"]}
tellraw @s [{"text":"Hid week 10's page \"Where Ruk Went\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w10,sort=nearest,limit=1]"}]
