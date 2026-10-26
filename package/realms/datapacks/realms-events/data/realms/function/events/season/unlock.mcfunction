# Undoes season/lock: survival, PvP and normal difficulty, as in server.properties.
scoreboard players set #season_locked ev.state 0
gamerule pvp true
difficulty normal
gamemode survival @a[gamemode=adventure]
tellraw @a {"text":"The world is unlocked.","color":"green"}
