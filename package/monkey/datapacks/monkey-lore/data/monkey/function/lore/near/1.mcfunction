# As week 1's hidden page, from week 1 on.
particle minecraft:enchant ~ ~0.5 ~ 0.3 0.6 0.3 0.4 6
execute as @a[distance=..4,gamemode=!spectator] unless score @s lr.w1 matches 1 run function monkey:lore/find/1
