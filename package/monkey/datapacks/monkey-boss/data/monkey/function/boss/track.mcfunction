# As the boss, at it: its health on the bar, for the players near it, and where it is.
execute store result bossbar monkey:boss value run data get entity @s Health
bossbar set monkey:boss players @a[distance=..96]
execute store result storage monkey:boss last.x int 1 run data get entity @s Pos[0]
execute store result storage monkey:boss last.z int 1 run data get entity @s Pos[2]
