scoreboard players set #raid ev.state 1
scoreboard players set #raid ev.timer 7200
bossbar set realms:raid max 7200
bossbar set realms:raid value 7200
bossbar set realms:raid color yellow
bossbar set realms:raid players @a
bossbar set realms:raid visible true
bossbar set realms:raid name {"text":"Faction Raid","color":"yellow"}
title @a times 10 60 20
title @a title {"text":"Faction Raid","color":"yellow"}
tellraw @a {"text":"The Faction Raid is on for 2 hours. Flags travel in your inventory only; every rule and ban applies.","color":"yellow"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
