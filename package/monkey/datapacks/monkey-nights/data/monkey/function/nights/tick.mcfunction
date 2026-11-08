scoreboard players remove #left nt.timer 1
execute store result bossbar monkey:nights value run scoreboard players get #left nt.timer
scoreboard players operation #sec nt.timer = #left nt.timer
scoreboard players operation #sec nt.timer %= #60 nt.timer
execute if score #sec nt.timer matches 0 run function monkey:nights/bar
execute if score #phase nt.state matches 1 if score #left nt.timer matches 600 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"PvP and the Nether open in 10 minutes.","color":"red"}]
execute if score #phase nt.state matches 1 if score #left nt.timer matches 300 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"PvP and the Nether open in 5 minutes. Get home!","color":"red"}]
execute if score #phase nt.state matches 1 if score #left nt.timer matches 60 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"PvP and the Nether open in 1 minute.","color":"red"}]
execute if score #phase nt.state matches 2 if score #left nt.timer matches 1800 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Rise of Kingdoms: 30 minutes of building left.","color":"yellow"}]
execute if score #phase nt.state matches 2 if score #left nt.timer matches 600 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Rise of Kingdoms: 10 minutes left. Finish your base!","color":"yellow"}]
execute if score #phase nt.state matches 2 if score #left nt.timer matches 60 run tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Rise of Kingdoms: 1 minute left.","color":"yellow"}]
execute if score #left nt.timer matches ..0 if score #phase nt.state matches 1 run return run function monkey:nights/grace/end
execute if score #left nt.timer matches ..0 if score #phase nt.state matches 2 run return run function monkey:nights/build/end
