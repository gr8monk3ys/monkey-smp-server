# Run as a player who turned up (the arena does it on join). Counts once per event.
execute if score @s ev.seen = #event ev.state run return 0
scoreboard players operation @s ev.seen = #event ev.state
scoreboard players add @s rw.events 1
