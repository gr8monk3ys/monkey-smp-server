# Returns 1 when it starts. Not when PvP is off already (the launch hour, the season lock, staff).
execute store result score #pvp om run gamerule pvp
execute unless score #pvp om matches 1 run return 0
execute if score #launching realms.rules matches 1 run return 0
gamerule pvp false
scoreboard players set #state om 3
scoreboard players set #timer om 3600
bossbar remove realms:omen
bossbar add realms:omen {"text":"Truce Hour","color":"green"}
bossbar set realms:omen color green
bossbar set realms:omen max 3600
bossbar set realms:omen value 3600
bossbar set realms:omen players @a
bossbar set realms:omen visible true
title @a times 10 60 20
title @a title {"text":"Truce Hour","color":"green","bold":true}
tellraw @a [{"text":"Truce Hour: ","color":"green","bold":true},{"text":"for the next 60 minutes no player can hurt another, anywhere. Claims and the rules work as always. PvP comes back on at the end.","color":"yellow"}]
execute as @a at @s run playsound minecraft:block.bell.use master @s ~ ~ ~ 1 0.8
return 1
