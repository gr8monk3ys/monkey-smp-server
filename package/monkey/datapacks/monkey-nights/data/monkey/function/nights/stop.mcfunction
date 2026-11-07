# Cancels whatever phase runs. Game rules stay as they are: check them after.
execute unless score #phase nt.state matches 1.. run return run tellraw @s [{"text":"Nothing is running.","color":"red"}]
scoreboard players set #phase nt.state 0
bossbar remove monkey:nights
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Staff stopped the event timer.","color":"gray"}]
tellraw @s [{"text":"Stopped. Game rules unchanged: check /gamerule pvp and /gamerule allow_entering_nether_using_portals.","color":"yellow"}]
