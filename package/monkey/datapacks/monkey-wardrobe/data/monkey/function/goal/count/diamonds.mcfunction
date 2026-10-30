# Mine diamond ore: the online players' counts since the last check go into the total, then start again.
# Creative and spectator players' are dropped.
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.diamonds.0
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.diamonds.1
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.diamonds.m0
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.diamonds.m1
scoreboard players reset @a rg.diamonds.0
scoreboard players reset @a rg.diamonds.1
scoreboard players reset @a rg.diamonds.m0
scoreboard players reset @a rg.diamonds.m1
