schedule function realms:events/second 20t replace
execute if score #arena ev.state matches 1 run scoreboard players enable @a arena
execute if score #anarchy ev.state matches 1.. run function realms:events/anarchy/second
execute if score #raid ev.state matches 1.. run function realms:events/raid/second
