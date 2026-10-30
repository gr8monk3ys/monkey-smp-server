# As week 9's hidden page, from week 9 on.
particle minecraft:enchant ~ ~0.5 ~ 0.3 0.6 0.3 0.4 6
execute as @a[distance=..4,gamemode=!spectator] unless score @s lr.w9 matches 1 run function monkey:lore/find/9
