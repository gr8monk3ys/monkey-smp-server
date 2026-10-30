schedule function monkey:lore/second 20t replace
execute unless score #on lr matches 1 run return 0
scoreboard players enable @a lore
execute as @a[scores={lore=1..}] run function monkey:lore/use
execute unless score #launched rw.day matches 1 run return 0
execute if score #week rc.week matches 1..11 unless score #told lr = #week rc.week run scoreboard players operation #told lr = #week rc.week
execute if score #told lr matches 1..11 as @a unless score @s lr.seen = #told lr run function monkey:lore/greet
execute as @e[type=minecraft:marker,tag=lore.cache] at @s run function monkey:lore/cache
