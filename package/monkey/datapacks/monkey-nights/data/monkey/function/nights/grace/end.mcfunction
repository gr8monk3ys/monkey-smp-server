# 6:30 PM (the countdown, the VPS, or an admin): PvP and the Nether open, then the build battle.
execute unless score #phase nt.state matches 1 run return run tellraw @s [{"text":"No grace period is running.","color":"red"}]
gamerule pvp true
gamerule allow_entering_nether_using_portals true
scoreboard players set #phase nt.state 0
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"The grace period is over: PvP and the Nether are open.","color":"red"}]
function monkey:nights/build/start
