scoreboard players set #anarchy ev.state 1
scoreboard players set #anarchy ev.timer 5400
bossbar set monkey:anarchy max 5400
bossbar set monkey:anarchy value 5400
bossbar set monkey:anarchy color red
bossbar set monkey:anarchy players @a
bossbar set monkey:anarchy visible true
bossbar set monkey:anarchy name {"text":"Anarchy","color":"red"}
title @a times 10 60 20
title @a title {"text":"Anarchy","color":"red"}
tellraw @a {"text":"Anarchy for 90 minutes: the combat rules and gameplay bans are off. Griefing, cheating and conduct rules still apply.","color":"red"}
playsound minecraft:event.raid.horn master @a ~ ~ ~ 1000 1
