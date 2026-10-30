# The event on now: the arena's entrance while it is open, else a supply drop's spot.
execute if score #arena ev.state matches 1 if data storage monkey:events arena.lx run return run function monkey:camera/warp/arena with storage monkey:events arena
execute if score #state dr matches 1.. if data storage monkey:drops spot.x run return run function monkey:camera/warp/drop
return run tellraw @s {"text":"No event on right now.","color":"red"}
