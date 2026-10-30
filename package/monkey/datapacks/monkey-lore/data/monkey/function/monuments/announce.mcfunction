# Macro: the winner, as kept in the hall.
title @a times 10 70 20
title @a subtitle {"nbt":"won.faction","storage":"monkey:monuments","interpret":true,"color":"gold"}
title @a title {"text":"Monument of the Month","color":"gold","bold":true}
$tellraw @a ["",{"nbt":"won.faction","storage":"monkey:monuments","interpret":true,"color":"gold"},{"text":" won the $(month) monument contest, $(theme)! ","color":"yellow"},{"text":"It stands at $(x) $(y) $(z), and it will be a warp next season.","color":"gray"}]
