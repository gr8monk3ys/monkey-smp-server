# Cancels the event timer: no "Event over" (timer/finish ends it now with one).
execute unless score #timer ev.state matches 1.. run return run tellraw @s {"text":"No event timer is running.","color":"red"}
scoreboard players set #timer ev.state 0
scoreboard players set #timer ev.timer 0
bossbar remove monkey:timer
tellraw @a [{"text":"Staff stopped the timer for ","color":"gray"},{"storage":"monkey:events","nbt":"timer.name","color":"gray"},{"text":".","color":"gray"}]
