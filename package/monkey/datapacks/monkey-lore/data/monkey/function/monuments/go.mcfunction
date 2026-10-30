$execute in $(dim) run tp @s $(x) $(y) $(z)
$tellraw @s ["",{"text":"Monument $(n): $(theme), $(month), by ","color":"gray"},{"nbt":"hall[{n:$(n)}].faction","storage":"monkey:monuments","interpret":true,"color":"gold"},{"text":".","color":"gray"}]
