# /trigger outposts: outpost 2's line.
execute unless score #o2 op.hold matches 1.. run tellraw @s ["",{"text":" - East at ","color":"gray"},{"nbt":"at.o2.x","storage":"realms:outposts","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"at.o2.z","storage":"realms:outposts","color":"aqua"},{"text":": nobody holds it","color":"gray"}]
execute if score #o2 op.hold matches 1.. run function realms:outposts/o/2/line_held
execute if score #o2 op.prog matches 1.. run tellraw @s {"text":"   someone is taking it right now","color":"gray"}
