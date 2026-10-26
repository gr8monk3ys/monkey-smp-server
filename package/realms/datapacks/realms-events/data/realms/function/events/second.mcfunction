schedule function realms:events/second 20t replace
execute if score #arena ev.state matches 1 run scoreboard players enable @a arena
execute if score #anarchy ev.state matches 1.. run function realms:events/anarchy/second
execute if score #raid ev.state matches 1.. run function realms:events/raid/second
# A locked season world: whoever logs in can look around but not change it.
execute if score #season_locked ev.state matches 1 run gamemode adventure @a[gamemode=survival]
