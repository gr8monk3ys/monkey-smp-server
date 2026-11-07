# Macro {name:"Boat Race",minutes:30}: starts the event timer. A name with a " in it, or minutes that are
# not a whole number, make the macro fail as a whole, so nothing below runs.
execute if score #timer ev.state matches 1.. run return run tellraw @s {"text":"An event timer is already running. /function monkey:events/timer/stop ends it early.","color":"red"}
$scoreboard players set #timer_new ev.timer $(minutes)
execute unless score #timer_new ev.timer matches 1..600 run return run tellraw @s {"text":"minutes must be 1 to 600.","color":"red"}
$data modify storage monkey:events timer.name set value "$(name)"
scoreboard players operation #timer ev.timer = #timer_new ev.timer
scoreboard players operation #timer ev.timer *= #60 ev.timer
scoreboard players set #timer ev.state 1
# A new event, so everyone who turns up (attend) is counted once for it.
scoreboard players add #event ev.state 1
bossbar remove monkey:timer
bossbar add monkey:timer {"text":"Event"}
execute store result bossbar monkey:timer max run scoreboard players get #timer ev.timer
execute store result bossbar monkey:timer value run scoreboard players get #timer ev.timer
bossbar set monkey:timer color blue
bossbar set monkey:timer players @a
bossbar set monkey:timer visible true
bossbar set monkey:timer name {"storage":"monkey:events","nbt":"timer.name","color":"aqua"}
title @a times 10 60 20
title @a subtitle [{"score":{"name":"#timer_new","objective":"ev.timer"},"color":"white"},{"text":" minutes on the clock","color":"gray"}]
title @a title {"storage":"monkey:events","nbt":"timer.name","color":"aqua"}
tellraw @a [{"storage":"monkey:events","nbt":"timer.name","color":"aqua"},{"text":" has started: ","color":"aqua"},{"score":{"name":"#timer_new","objective":"ev.timer"},"color":"white"},{"text":" minutes on the clock.","color":"aqua"}]
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
