scoreboard players set #anarchy ev.state 1
scoreboard players set #anarchy ev.timer 5400
bossbar set realms:anarchy max 5400
bossbar set realms:anarchy value 5400
bossbar set realms:anarchy color red
bossbar set realms:anarchy players @a
bossbar set realms:anarchy visible true
bossbar set realms:anarchy name {"text":"Anarchy","color":"red"}
title @a times 10 60 20
title @a title {"text":"Anarchy","color":"red"}
tellraw @a {"text":"Anarchy for 90 minutes: the combat rules and gameplay bans are off. Griefing, cheating and conduct rules still apply.","color":"red"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
