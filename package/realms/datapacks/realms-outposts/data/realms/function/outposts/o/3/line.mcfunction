# /trigger outposts: outpost 3's line.
execute unless score #o3 op.hold matches 1.. run tellraw @s ["",{"text":" - South at ","color":"gray"},{"nbt":"at.o3.x","storage":"realms:outposts","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"at.o3.z","storage":"realms:outposts","color":"aqua"},{"text":": nobody holds it","color":"gray"}]
execute if score #o3 op.hold matches 1.. run function realms:outposts/o/3/line_held
execute if score #o3 op.prog matches 1.. run tellraw @s {"text":"   someone is taking it right now","color":"gray"}
