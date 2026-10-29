# Staff: a drop where you stand (in the Overworld: Nether or End coordinates would put it elsewhere).
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"Supply drops land in the Overworld: stand there, or use /function monkey:drops/start {x:0,z:0}.","color":"red"}
execute store result storage monkey:drops here.x int 1 run data get entity @s Pos[0]
execute store result storage monkey:drops here.z int 1 run data get entity @s Pos[2]
function monkey:drops/start with storage monkey:drops here
