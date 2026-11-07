# 9:30 PM (the countdown, the VPS, or an admin): building stops, staff judge.
execute unless score #phase nt.state matches 2 run return run tellraw @s [{"text":"No build battle is running.","color":"red"}]
scoreboard players set #phase nt.state 0
bossbar remove monkey:nights
title @a times 10 80 20
title @a subtitle {"text":"Staff are judging the bases now","color":"yellow"}
title @a title {"text":"Building is over","color":"gold"}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Rise of Kingdoms is over. Thanks for building! Staff will judge and hand out the rewards.","color":"gold"}]
