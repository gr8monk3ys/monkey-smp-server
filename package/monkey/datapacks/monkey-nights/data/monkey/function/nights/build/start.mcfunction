# Rise of Kingdoms: 3 hours, judged by staff per faction at the end.
execute if score #phase nt.state matches 1.. run return run tellraw @s [{"text":"An event night phase is already running. /function monkey:nights/stop cancels it.","color":"red"}]
scoreboard players set #phase nt.state 2
bossbar remove monkey:nights
bossbar add monkey:nights {"text":"Monkey SMP"}
bossbar set monkey:nights color yellow
bossbar set monkey:nights max 10800
bossbar set monkey:nights value 10800
bossbar set monkey:nights visible true
scoreboard players set #left nt.timer 10800
function monkey:nights/bar
title @a times 10 80 20
title @a subtitle {"text":"PvP and the Nether are open. Build until 9:30!","color":"red"}
title @a title {"text":"Rise of Kingdoms","color":"gold"}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 1 1
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Rise of Kingdoms has started! Staff judge each faction's base at the end:","color":"yellow"}]
tellraw @a [{"text":" custom faction banner (1-3), a full 3-high custom wall around your land (1-3), animal farm (1-2), trading post (1-2), house (1-5), automated build (1-3), rare items (1-4), and 2 points for each block we call out tonight.","color":"gray"}]
tellraw @a [{"text":" Prizes: a mace, a smithing template and 64 golden apples, plus +1 Strength.","color":"gray"}]
