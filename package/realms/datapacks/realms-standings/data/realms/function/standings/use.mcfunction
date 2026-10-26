# Runs as a player who used /trigger standings.
scoreboard players set @s standings 0
scoreboard players enable @s standings
tellraw @s {"nbt":"board","storage":"realms:standings","interpret":true}
