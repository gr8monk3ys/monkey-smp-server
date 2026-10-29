scoreboard players remove #timer om 1
scoreboard players operation #mins om = #timer om
scoreboard players add #mins om 59
scoreboard players operation #mins om /= #60 om
execute store result bossbar realms:omen value run scoreboard players get #timer om
bossbar set realms:omen players @a
bossbar set realms:omen name [{"text":"","color":"red"},{"text":"Hunted: ","bold":true},{"nbt":"target.name","storage":"realms:omens","color":"white"},{"text":" for "},{"score":{"name":"#mins","objective":"om"},"color":"white"},{"text":" min","color":"red"}]
execute unless entity @a[scores={om.hunt=1..}] run return run function realms:omens/hunted/left
execute if score #timer om matches ..0 run function realms:omens/hunted/survived
