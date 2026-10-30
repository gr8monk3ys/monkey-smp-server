scoreboard players set #open sg 1
# The minute it opened and closed: tools/news.py's Discord posts read them from the saved world.
scoreboard players operation #opened sg = #now sg
scoreboard players set #w1 sg 1
scoreboard players set #w2 sg 1
tellraw @a ["",{"text":"The siege window is open","color":"red","bold":true},{"text":" (","color":"gray"},{"nbt":"label","storage":"monkey:sieges","color":"yellow"},{"text":"). The four outposts are the prize: a capture while it is open earns your faction a bonus hour held. It's a staff event: inside an outpost's square anyone can fight anyone (rule 41). Faction claims stay protected and every other rule still applies, lava included. /trigger outposts says where they are.","color":"gray"}]
title @a times 10 60 20
title @a subtitle {"text":"Capture an outpost for a bonus hour","color":"gray"}
title @a title {"text":"Outpost siege open","color":"red"}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1
