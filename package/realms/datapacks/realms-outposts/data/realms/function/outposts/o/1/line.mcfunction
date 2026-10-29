# /trigger outposts: outpost 1's line.
execute unless score #o1 op.hold matches 1.. run tellraw @s ["",{"text":" - North at ","color":"gray"},{"nbt":"at.o1.x","storage":"realms:outposts","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"at.o1.z","storage":"realms:outposts","color":"aqua"},{"text":": nobody holds it","color":"gray"}]
execute if score #o1 op.hold matches 1.. run function realms:outposts/o/1/line_held
execute if score #o1 op.prog matches 1.. run tellraw @s {"text":"   someone is taking it right now","color":"gray"}
