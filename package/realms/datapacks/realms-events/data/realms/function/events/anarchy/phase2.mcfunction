scoreboard players set #anarchy ev.state 2
scoreboard players set #anarchy ev.timer 600
bossbar set realms:anarchy max 600
bossbar set realms:anarchy value 600
bossbar set realms:anarchy color green
bossbar set realms:anarchy players @a
bossbar set realms:anarchy visible true
bossbar set realms:anarchy name {"text":"Ceasefire","color":"green"}
title @a times 10 60 20
title @a title {"text":"Ceasefire","color":"green"}
tellraw @a {"text":"Anarchy is over. 10-minute ceasefire: no fighting. Take down your traps and get rid of totems, end crystals and enchanted golden apples.","color":"green"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
