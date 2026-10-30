# Mine ancient debris: the online players' counts since the last check go into the total, then start again.
# Creative and spectator players' are dropped.
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.debris.0
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.debris.m0
scoreboard players reset @a rg.debris.0
scoreboard players reset @a rg.debris.m0
