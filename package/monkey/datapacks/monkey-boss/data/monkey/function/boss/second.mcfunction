schedule function monkey:boss/second 20t replace
# A boss from one that ended (it was in an unloaded chunk then) goes as soon as it is seen.
execute unless score #state bs matches 2 as @e[type=minecraft:wither_skeleton,tag=monkey.boss] run function monkey:boss/vanish
execute if score #state bs matches 1 run function monkey:boss/waiting
execute if score #state bs matches 2 run function monkey:boss/up
