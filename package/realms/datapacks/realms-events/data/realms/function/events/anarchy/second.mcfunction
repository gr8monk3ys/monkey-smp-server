scoreboard players remove #anarchy ev.timer 1
execute store result bossbar realms:anarchy value run scoreboard players get #anarchy ev.timer
scoreboard players operation #anarchy_min ev.timer = #anarchy ev.timer
scoreboard players add #anarchy_min ev.timer 59
scoreboard players operation #anarchy_min ev.timer /= #60 ev.timer
bossbar set realms:anarchy players @a
execute if score #anarchy ev.state matches 1 run bossbar set realms:anarchy name [{"text":"Anarchy: ","color":"red"},{"score":{"name":"#anarchy_min","objective":"ev.timer"},"color":"white"},{"text":" min left","color":"red"}]
execute if score #anarchy ev.state matches 2 run bossbar set realms:anarchy name [{"text":"Ceasefire: ","color":"green"},{"score":{"name":"#anarchy_min","objective":"ev.timer"},"color":"white"},{"text":" min left","color":"green"}]
execute if score #anarchy ev.state matches 1 if score #anarchy ev.timer matches 600 run tellraw @a {"text":"Anarchy: 10 minutes left.","color":"red"}
execute if score #anarchy ev.state matches 1 if score #anarchy ev.timer matches 300 run tellraw @a {"text":"Anarchy: 5 minutes left.","color":"red"}
execute if score #anarchy ev.state matches 1 if score #anarchy ev.timer matches 60 run tellraw @a {"text":"Anarchy: 1 minute left.","color":"red"}
execute if score #anarchy ev.state matches 1 if score #anarchy ev.timer matches ..0 run return run function realms:events/anarchy/phase2
execute if score #anarchy ev.state matches 2 if score #anarchy ev.timer matches ..0 run return run function realms:events/anarchy/over
