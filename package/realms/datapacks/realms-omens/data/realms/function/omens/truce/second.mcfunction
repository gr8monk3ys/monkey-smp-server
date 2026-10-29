scoreboard players remove #timer om 1
scoreboard players operation #mins om = #timer om
scoreboard players add #mins om 59
scoreboard players operation #mins om /= #60 om
execute store result bossbar realms:omen value run scoreboard players get #timer om
bossbar set realms:omen players @a
bossbar set realms:omen name [{"text":"","color":"green"},{"text":"Truce Hour: ","bold":true},{"text":"no PvP for "},{"score":{"name":"#mins","objective":"om"},"color":"white"},{"text":" min","color":"green"}]
execute if score #timer om matches 300 run tellraw @a [{"text":"Truce Hour: ","color":"green","bold":true},{"text":"5 minutes until PvP is back on.","color":"yellow"}]
execute if score #timer om matches ..0 run function realms:omens/truce/over
