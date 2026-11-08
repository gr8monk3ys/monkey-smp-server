# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"): upstream ran 16 world-wide
# @e[type=item,name="<Color> Dye"] scans every tick, one per dye. The pass at the bottom now visits each item
# entity once, keeps only dyes not yet a trim material, and runs this function again as that item: the lines
# just below then set its material, as upstream's `data merge` did.
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:red_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:red"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:orange_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:orange"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:yellow_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:yellow"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:green_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:green"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:lime_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:lime"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:cyan_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:cyan"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:light_blue_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:light_blue"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:blue_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:blue"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:purple_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:purple"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:magenta_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:magenta"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:pink_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:pink"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:white_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:white"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:light_gray_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:light_gray"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:gray_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:gray"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:black_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:black"}}}
execute if entity @s[type=minecraft:item] if items entity @s contents minecraft:brown_dye run return run data merge entity @s {Item:{components:{"minecraft:provides_trim_material":"colorful_trims:brown"}}}
execute if entity @s run return 0

execute as @a if items entity @s container.* #colorful_trims:dyes[!minecraft:provides_trim_material] run function colorful_trims:fix_dyes
execute as @a if items entity @s player.cursor #colorful_trims:dyes[!minecraft:provides_trim_material] run function colorful_trims:fix_dyes
execute as @a if items entity @s weapon.offhand #colorful_trims:dyes[!minecraft:provides_trim_material] run function colorful_trims:fix_dyes

execute as @e[type=minecraft:item] if items entity @s contents #colorful_trims:dyes[!minecraft:provides_trim_material] run function colorful_trims:tick
