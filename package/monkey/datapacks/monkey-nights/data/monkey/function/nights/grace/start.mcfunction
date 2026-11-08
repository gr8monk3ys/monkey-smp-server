# 5:00 PM (sent by the VPS, or an admin runs it): the 90-minute grace period.
function monkey:nights/load
execute if score #phase nt.state matches 1.. run return run tellraw @s [{"text":"An event night phase is already running. /function monkey:nights/stop cancels it.","color":"red"}]
gamerule pvp false
gamerule allow_entering_nether_using_portals false
scoreboard players set #phase nt.state 1
bossbar remove monkey:nights
bossbar add monkey:nights {"text":"Monkey SMP"}
bossbar set monkey:nights color green
bossbar set monkey:nights max 5400
bossbar set monkey:nights value 5400
bossbar set monkey:nights visible true
scoreboard players set #left nt.timer 5400
function monkey:nights/bar
title @a times 10 80 20
title @a subtitle {"text":"Grace: no PvP, Nether closed for 90 minutes","color":"yellow"}
title @a title {"text":"The Path To Strength","color":"gold"}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 1 1
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Season I has begun! For 90 minutes there is no PvP and the Nether is closed. Make your faction with ","color":"yellow"},{"text":"/oparties create","color":"aqua"},{"text":", name it with ","color":"yellow"},{"text":"/opac player-config set parties.name <name>","color":"aqua"},{"text":", and claim your land with ","color":"yellow"},{"text":"/oclaims","color":"aqua"},{"text":". At 6:30 the Rise of Kingdoms build battle starts.","color":"yellow"}]
