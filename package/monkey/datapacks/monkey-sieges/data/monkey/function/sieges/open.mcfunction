scoreboard players set #open sg 1
# The minute it opened and closed: tools/news.py's Discord posts read them from the saved world.
scoreboard players operation #opened sg = #now sg
scoreboard players set #w1 sg 1
scoreboard players set #w2 sg 1
function monkey:sieges/unlock
tellraw @a ["",{"text":"The siege window is open","color":"red","bold":true},{"text":" (","color":"gray"},{"nbt":"label","storage":"monkey:sieges","color":"yellow"},{"text":"). Outside your own party, anyone can break blocks, open chests and doors, place blocks and set off TNT in any faction's claims. Spawn and the wilderness are as always, and so are animals, item frames and villagers in claims. The other rules still apply.","color":"gray"}]
title @a times 10 60 20
title @a subtitle {"text":"Claims can be raided until it closes","color":"gray"}
title @a title {"text":"Siege window open","color":"red"}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.6 1
