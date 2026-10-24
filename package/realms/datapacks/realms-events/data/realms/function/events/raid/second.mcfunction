scoreboard players remove #raid ev.timer 1
execute store result bossbar realms:raid value run scoreboard players get #raid ev.timer
scoreboard players operation #raid_min ev.timer = #raid ev.timer
scoreboard players add #raid_min ev.timer 59
scoreboard players operation #raid_min ev.timer /= #60 ev.timer
bossbar set realms:raid players @a
execute if score #raid ev.state matches 1 run bossbar set realms:raid name [{"text":"Faction Raid: ","color":"yellow"},{"score":{"name":"#raid_min","objective":"ev.timer"},"color":"white"},{"text":" min left","color":"yellow"}]
execute if score #raid ev.state matches 1 if score #raid ev.timer matches 600 run tellraw @a {"text":"Faction Raid: 10 minutes left.","color":"yellow"}
execute if score #raid ev.state matches 1 if score #raid ev.timer matches 300 run tellraw @a {"text":"Faction Raid: 5 minutes left.","color":"yellow"}
execute if score #raid ev.state matches 1 if score #raid ev.timer matches 60 run tellraw @a {"text":"Faction Raid: 1 minute left.","color":"yellow"}
execute if score #raid ev.state matches 1 if score #raid ev.timer matches ..0 run return run function realms:events/raid/over
