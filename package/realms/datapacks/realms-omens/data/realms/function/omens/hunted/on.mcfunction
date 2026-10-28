# Macro {name:"Alex"}: the hunt on Alex starts (the name is in storage target too).
scoreboard players reset * om.hunt
$scoreboard players set $(name) om.hunt 1
scoreboard players set #state om 4
scoreboard players set #timer om 1800
bossbar remove realms:omen
bossbar add realms:omen {"text":"Hunted","color":"red"}
bossbar set realms:omen color red
bossbar set realms:omen max 1800
bossbar set realms:omen value 1800
bossbar set realms:omen players @a
bossbar set realms:omen visible true
title @a times 10 60 20
title @a title {"text":"Hunted","color":"red","bold":true}
$title @a subtitle {"text":"$(name)","color":"white"}
$tellraw @a [{"text":"Hunted: ","color":"red","bold":true},{"text":"$(name)","color":"white"},{"text":" is hunted (kills in a row without dying: ","color":"yellow"},{"score":{"name":"$(name)","objective":"om.streak"},"color":"aqua"},{"text":"). For the next 30 minutes there is a bounty on them. $(name): stay alive.","color":"yellow"}]
$function realms:standings/bounty/post {target:"$(name)"}
execute as @a at @s run playsound minecraft:entity.wolf.howl master @s ~ ~ ~ 0.6 0.9
