# Chop logs: the online players' counts since the last check go into the total, then start again.
# Creative and spectator players' are dropped.
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.0
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.1
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.2
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.3
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.4
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.5
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.6
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.7
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.8
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.9
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.logs.10
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m0
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m1
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m2
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m3
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m4
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m5
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m6
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m7
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m8
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m9
scoreboard players operation #total rg -= @a[gamemode=!creative,gamemode=!spectator] rg.logs.m10
scoreboard players reset @a rg.logs.0
scoreboard players reset @a rg.logs.1
scoreboard players reset @a rg.logs.2
scoreboard players reset @a rg.logs.3
scoreboard players reset @a rg.logs.4
scoreboard players reset @a rg.logs.5
scoreboard players reset @a rg.logs.6
scoreboard players reset @a rg.logs.7
scoreboard players reset @a rg.logs.8
scoreboard players reset @a rg.logs.9
scoreboard players reset @a rg.logs.10
scoreboard players reset @a rg.logs.m0
scoreboard players reset @a rg.logs.m1
scoreboard players reset @a rg.logs.m2
scoreboard players reset @a rg.logs.m3
scoreboard players reset @a rg.logs.m4
scoreboard players reset @a rg.logs.m5
scoreboard players reset @a rg.logs.m6
scoreboard players reset @a rg.logs.m7
scoreboard players reset @a rg.logs.m8
scoreboard players reset @a rg.logs.m9
scoreboard players reset @a rg.logs.m10
