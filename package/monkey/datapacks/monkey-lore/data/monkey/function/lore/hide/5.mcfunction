# Staff, in game, standing where it goes: hides week 5's page, "The Deep Metal" (in the Nether, near a portal).
# It shows and can be found from week 5. Run it again elsewhere to add a second spot for it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.
execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["lore.cache","lore.w5"]}
tellraw @s [{"text":"Hid week 5's page \"The Deep Metal\" here: ","color":"green"},{"nbt":"Pos","color":"white","entity":"@e[type=minecraft:marker,tag=lore.w5,sort=nearest,limit=1]"}]
