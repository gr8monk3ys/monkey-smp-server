# Nightfall: Hard until dawn (the difficulty it was on comes back then).
execute store result score #diff om run difficulty
difficulty hard
scoreboard players set #phase om 1
scoreboard players set #timer om 900
scoreboard players reset * om.loot
bossbar remove realms:omen
bossbar add realms:omen {"text":"Blood Moon","color":"red"}
bossbar set realms:omen color red
bossbar set realms:omen max 900
bossbar set realms:omen value 900
bossbar set realms:omen players @a
bossbar set realms:omen visible true
title @a times 10 60 20
title @a subtitle {"text":"until dawn","color":"red"}
title @a title {"text":"Blood Moon","color":"dark_red","bold":true}
tellraw @a [{"text":"Blood Moon: ","color":"dark_red","bold":true},{"text":"until dawn the game is on Hard, and mobs near players are faster and tougher. Each one you kill drops a little extra (up to 20 each). Sleeping through the night ends it.","color":"red"}]
execute as @a at @s run playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.4 0.6
