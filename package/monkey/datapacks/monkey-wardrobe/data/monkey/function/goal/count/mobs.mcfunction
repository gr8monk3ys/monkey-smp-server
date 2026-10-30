# Defeat mobs: the online players' counts since the last check go into the total, then start again.
# Creative and spectator players' are dropped.
scoreboard players operation #total rg += @a[gamemode=!creative,gamemode=!spectator] rg.mobs.0
scoreboard players reset @a rg.mobs.0
