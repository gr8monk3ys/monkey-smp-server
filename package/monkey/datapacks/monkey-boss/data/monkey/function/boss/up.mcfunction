execute store result score #seen bs if entity @e[type=minecraft:wither_skeleton,tag=monkey.boss]
execute if score #seen bs matches 1.. as @e[type=minecraft:wither_skeleton,tag=monkey.boss,limit=1] at @s run function monkey:boss/track
# Not found: in a chunk nobody has loaded (it waits), or dead without a player's kill.
execute if score #seen bs matches 0 run function monkey:boss/missing with storage monkey:boss last
execute unless score #state bs matches 2 run return 0
scoreboard players remove #left bs 1
execute if score #left bs matches 600 run tellraw @a {"text":"The Edgewalker leaves in 10 minutes.","color":"gold"}
execute if score #left bs matches ..0 run function monkey:boss/leave
