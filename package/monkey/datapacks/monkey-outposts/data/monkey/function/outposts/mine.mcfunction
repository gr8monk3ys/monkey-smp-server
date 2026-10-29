# Macro {f}: the player's faction's hours held this season.
scoreboard players set #h op 0
$scoreboard players operation #h op = #f$(f) op.min
scoreboard players operation #h op /= #60 op
tellraw @s ["",{"text":"Your faction has held outposts for ","color":"gray"},{"score":{"name":"#h","objective":"op"},"color":"white"},{"text":" hours this season (the hours that count).","color":"gray"}]
