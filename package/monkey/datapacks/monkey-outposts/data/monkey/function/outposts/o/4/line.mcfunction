# /trigger outposts: outpost 4's line.
execute unless score #o4 op.hold matches 1.. run tellraw @s ["",{"text":" - West at ","color":"gray"},{"nbt":"at.o4.x","storage":"monkey:outposts","color":"aqua"},{"text":", ","color":"aqua"},{"nbt":"at.o4.z","storage":"monkey:outposts","color":"aqua"},{"text":": nobody holds it","color":"gray"}]
execute if score #o4 op.hold matches 1.. run function monkey:outposts/o/4/line_held
execute if score #o4 op.prog matches 1.. run tellraw @s {"text":"   someone is taking it right now","color":"gray"}
