scoreboard players set #arena ev.state 0
execute as @e[type=player,tag=ev.arena] run function realms:events/arena/leave with storage realms:events arena
function realms:events/arena/round with storage realms:events arena
tellraw @a {"text":"Arena Glory is closed. Thanks for fighting.","color":"gold"}
