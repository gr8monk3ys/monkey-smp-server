scoreboard players set #arena ev.state 0
execute as @e[type=player,tag=ev.arena] run function monkey:events/arena/leave with storage monkey:events arena
function monkey:events/arena/round with storage monkey:events arena
tellraw @a {"text":"Arena Glory is closed. Thanks for fighting.","color":"gold"}
