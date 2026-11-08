execute align xyz positioned ~0.5 ~ ~0.5 run summon minecraft:marker ~ ~ ~ {Tags:["gsg.light","gsg.light.mark"]}
# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"): upstream found the marker it just summoned
# with a world-wide @e scan, once per glow squid per tick. Only that marker has gsg.light (search removes the tag),
# so look for it where it was summoned.
execute align xyz positioned ~0.5 ~ ~0.5 as @e[type=minecraft:marker,tag=gsg.light,distance=..0.01] at @s run function gsg:search
