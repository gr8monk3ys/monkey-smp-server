# The event's time is up: the title, a sound, and a line saying the Cup points come from staff.
scoreboard players set #timer ev.state 0
scoreboard players set #timer ev.timer 0
bossbar remove monkey:timer
title @a times 10 70 20
title @a subtitle {"storage":"monkey:events","nbt":"timer.name","color":"aqua"}
title @a title {"text":"Event over","color":"gold"}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
tellraw @a [{"storage":"monkey:events","nbt":"timer.name","color":"gold"},{"text":" is over. Thanks for playing! Staff will add the Season Cup points.","color":"gold"}]
