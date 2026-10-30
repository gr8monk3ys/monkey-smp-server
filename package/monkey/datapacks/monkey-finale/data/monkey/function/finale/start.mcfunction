# Macro {x, z, cx, cz}: the monument, and the Overworld border's centre now (it moves to the monument
# during the shrink, STEER blocks a second each way, so the border closes on it).
# Sent by the border timer (tools/border.py) at the finale's time, or by staff. Once a world.
execute unless score #on fn matches 1 run return 10
execute unless score #season rw.day matches 2.. run return 11
execute unless score #launched rw.day matches 1 run return 12
execute if score #season_locked ev.state matches 1 run return 13
execute if score #started fn matches 1 run return 14
# The monument within reach of the shrink: |x - cx| and |z - cz| at most SHRINK_SECONDS * STEER.
$scoreboard players set #a fn $(x)
$scoreboard players set #k fn $(cx)
scoreboard players operation #a fn -= #k fn
$scoreboard players set #b fn $(z)
$scoreboard players set #k fn $(cz)
scoreboard players operation #b fn -= #k fn
execute unless score #a fn matches -2400..2400 run return 15
execute unless score #b fn matches -2400..2400 run return 15
scoreboard players set #started fn 1
scoreboard players set #phase fn 1
scoreboard players set #t fn 0
scoreboard players set #edge fn 0
$data modify storage monkey:finale at set value {x:$(x),z:$(z),x0:$(x),z0:$(z),d:48,bx:$(cx),bz:$(cz)}
$scoreboard players set #mx fn $(x)
$scoreboard players set #mz fn $(z)
$scoreboard players set #bx fn $(cx)
$scoreboard players set #bz fn $(cz)
$scoreboard players set #cx fn $(x)
$scoreboard players set #cz fn $(z)
execute store result storage monkey:finale at.x0 int 1 run scoreboard players remove #cx fn 24
execute store result storage monkey:finale at.z0 int 1 run scoreboard players remove #cz fn 24
bossbar set monkey:finale players @a
bossbar set monkey:finale visible true
execute store result bossbar monkey:finale value run scoreboard players get #t fn
$tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"in 10 minutes the border starts closing on the monument at ","color":"gold"},{"text":"$(x), $(z)","color":"yellow"},{"text":", down to 256 blocks across over 40 minutes. Then the last hour, a staff event: the faction with the most member-time at the monument (within 24 blocks) holds it and wins. Within 64 blocks of it anyone can fight anyone (rule 41). Spawn stays safe.","color":"gold"}]
return 1
