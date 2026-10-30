# Staff: no boss on the next act; one that is up or waiting leaves now.
scoreboard players set #on bs 0
execute if score #state bs matches 2 run function monkey:boss/record {state:"left"}
execute if score #state bs matches 1 run function monkey:boss/record {state:"off"}
execute as @e[type=minecraft:wither_skeleton,tag=monkey.boss] run function monkey:boss/vanish
execute if score #state bs matches 1.. run function monkey:boss/end
tellraw @s {"text":"The border boss is off.","color":"gold"}
