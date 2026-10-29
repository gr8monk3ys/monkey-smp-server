# /trigger arena: 1 joins, 2 leaves.
execute if score @s arena matches 1 unless score #arena ev.state matches 1 run tellraw @s {"text":"The arena is closed.","color":"red"}
execute if score @s arena matches 1 if score #arena ev.state matches 1 run function monkey:events/arena/join with storage monkey:events arena
execute if score @s arena matches 2 if entity @s[tag=ev.arena] run function monkey:events/arena/leave with storage monkey:events arena
scoreboard players set @s arena 0
