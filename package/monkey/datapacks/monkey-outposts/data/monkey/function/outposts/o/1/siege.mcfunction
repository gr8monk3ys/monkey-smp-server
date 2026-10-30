# Macro {c}: a capture during an open siege window (tools/sieges.py). The faction gets a bonus, once for
# this outpost in this window (a window is known by the minute it opened).
$execute if score #s1.$(c) op.sg = #opened sg run return 0
$scoreboard players operation #s1.$(c) op.sg = #opened sg
$scoreboard players add #f$(c) op.min 60
$tellraw @a ["",{"text":"Outposts: ","color":"gold","bold":true},{"nbt":"names.f$(c)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" took the North outpost in a siege: a bonus 60 minutes held.","color":"gold"}]
