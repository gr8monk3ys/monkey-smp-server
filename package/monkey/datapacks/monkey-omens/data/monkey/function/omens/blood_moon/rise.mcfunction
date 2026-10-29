# Nightfall: Hard until dawn (the difficulty it was on comes back then). Staff set Peaceful since it
# was announced: no mobs, so it fades.
execute store result score #diff om run difficulty
execute if score #diff om matches 0 run return run function monkey:omens/blood_moon/fade
# This moon's number: a mob roused tonight carries it (om.blood), so one roused at an earlier moon and
# never calmed (its chunk was unloaded) pays nothing.
scoreboard players add #moon om 1
difficulty hard
scoreboard players set #phase om 1
scoreboard players set #timer om 900
scoreboard players reset * om.loot
bossbar remove monkey:omen
bossbar add monkey:omen {"text":"Blood Moon","color":"red"}
bossbar set monkey:omen color red
bossbar set monkey:omen max 900
bossbar set monkey:omen value 900
bossbar set monkey:omen players @a
bossbar set monkey:omen visible true
title @a times 10 60 20
title @a subtitle {"text":"until dawn","color":"red"}
title @a title {"text":"Blood Moon","color":"dark_red","bold":true}
tellraw @a [{"text":"Blood Moon: ","color":"dark_red","bold":true},{"text":"until dawn the game is on Hard, and mobs near players are faster and tougher. Each one you kill drops a little extra (up to 20 each). Sleeping through the night ends it.","color":"red"}]
execute as @a at @s run playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.4 0.6
