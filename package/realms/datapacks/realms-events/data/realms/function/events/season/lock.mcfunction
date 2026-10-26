# Locks the world at the end of a season. Undo with season/unlock.
scoreboard players set #season_locked ev.state 1
gamerule pvp false
difficulty peaceful
gamemode adventure @a[gamemode=survival]
tellraw @a [{"text":"The season is over and the world is locked for the archive. ","color":"gold"},{"text":"Look around and take screenshots: building, breaking and fighting are off. The download goes up in Discord soon.","color":"yellow"}]
