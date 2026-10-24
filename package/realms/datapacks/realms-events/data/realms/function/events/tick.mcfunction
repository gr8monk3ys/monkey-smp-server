execute if score #arena ev.state matches 1 run function realms:events/arena/tick with storage realms:events arena
execute as @a[scores={arena=1..}] run function realms:events/arena/use
# Anyone still marked as in the arena once it has closed (they were dead or offline when it did).
execute unless score #arena ev.state matches 1 as @e[type=player,tag=ev.arena] run function realms:events/arena/leave with storage realms:events arena
execute as @e[type=player,scores={ev.left=1..}] run function realms:events/rejoined
