scoreboard players set #raid ev.state 1
scoreboard players set #raid ev.timer 7200
bossbar set monkey:raid max 7200
bossbar set monkey:raid value 7200
bossbar set monkey:raid color yellow
bossbar set monkey:raid players @a
bossbar set monkey:raid visible true
bossbar set monkey:raid name {"text":"Faction Raid","color":"yellow"}
title @a times 10 60 20
title @a title {"text":"Faction Raid","color":"yellow"}
tellraw @a {"text":"The Faction Raid is on for 2 hours. Flags travel in your inventory only; every rule and ban applies.","color":"yellow"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
