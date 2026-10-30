# Macro {kind, title, other}: a big moment, as and at its player (or at a place, as the server).
# other: a second player's name, or "". Writes one MONKEY-CLIP line in the log (tools/clips.py).
execute unless score #on cl matches 1 run return 0
$data modify storage monkey:clips m set value {kind:"$(kind)",title:"$(title)",players:"",factions:"",dim:"overworld",name:""}
execute store result storage monkey:clips m.k1 int 1 run scoreboard players get #key1 cl
execute store result storage monkey:clips m.k2 int 1 run scoreboard players get #key2 cl
execute if dimension minecraft:the_nether run data modify storage monkey:clips m.dim set value "the_nether"
execute if dimension minecraft:the_end run data modify storage monkey:clips m.dim set value "the_end"
summon minecraft:marker ~ ~ ~ {Tags:["cl.here"]}
execute store result storage monkey:clips m.x int 1 run data get entity @n[type=minecraft:marker,tag=cl.here] Pos[0]
execute store result storage monkey:clips m.y int 1 run data get entity @n[type=minecraft:marker,tag=cl.here] Pos[1]
execute store result storage monkey:clips m.z int 1 run data get entity @n[type=minecraft:marker,tag=cl.here] Pos[2]
kill @e[type=minecraft:marker,tag=cl.here]
execute if entity @s[type=minecraft:player] run function monkey:clips/self
$data modify storage monkey:clips m.name set value "$(other)"
execute unless data storage monkey:clips m{name:""} run function monkey:clips/add with storage monkey:clips m
function monkey:clips/log with storage monkey:clips m
