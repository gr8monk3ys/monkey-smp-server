scoreboard players operation #min nt.timer = #left nt.timer
scoreboard players add #min nt.timer 59
scoreboard players operation #min nt.timer /= #60 nt.timer
execute if score #phase nt.state matches 1 run bossbar set monkey:nights name [{"text":"Grace period: ","color":"green"},{"score":{"name":"#min","objective":"nt.timer"},"color":"white"},{"text":" min left  |  no PvP, Nether closed","color":"green"}]
execute if score #phase nt.state matches 2 run bossbar set monkey:nights name [{"text":"Rise of Kingdoms: ","color":"gold"},{"score":{"name":"#min","objective":"nt.timer"},"color":"white"},{"text":" min of building left","color":"gold"}]
bossbar set monkey:nights players @a
