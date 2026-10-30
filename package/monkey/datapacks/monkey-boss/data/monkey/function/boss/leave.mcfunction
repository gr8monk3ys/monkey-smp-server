function monkey:boss/record {state:"left"}
execute as @e[type=minecraft:wither_skeleton,tag=monkey.boss] at @s run particle minecraft:large_smoke ~ ~2 ~ 1 2 1 0.05 200 force
execute as @e[type=minecraft:wither_skeleton,tag=monkey.boss] run function monkey:boss/vanish
tellraw @a {"text":"The Edgewalker slips back past the edge. Nobody slew it this time.","color":"gold"}
function monkey:boss/end
