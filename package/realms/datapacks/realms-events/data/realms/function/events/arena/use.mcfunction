# /trigger arena: 1 joins, 2 leaves.
execute if score @s arena matches 1 unless score #arena ev.state matches 1 run tellraw @s {"text":"The arena is closed.","color":"red"}
execute if score @s arena matches 1 if score #arena ev.state matches 1 run function realms:events/arena/join with storage realms:events arena
execute if score @s arena matches 2 if entity @s[tag=ev.arena] run function realms:events/arena/leave with storage realms:events arena
scoreboard players set @s arena 0
