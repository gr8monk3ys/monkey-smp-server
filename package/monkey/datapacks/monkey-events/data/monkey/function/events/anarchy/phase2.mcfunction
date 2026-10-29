scoreboard players set #anarchy ev.state 2
scoreboard players set #anarchy ev.timer 600
bossbar set monkey:anarchy max 600
bossbar set monkey:anarchy value 600
bossbar set monkey:anarchy color green
bossbar set monkey:anarchy players @a
bossbar set monkey:anarchy visible true
bossbar set monkey:anarchy name {"text":"Ceasefire","color":"green"}
title @a times 10 60 20
title @a title {"text":"Ceasefire","color":"green"}
tellraw @a {"text":"Anarchy is over. 10-minute ceasefire: no fighting. Take down your traps and get rid of totems, end crystals and enchanted golden apples.","color":"green"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
