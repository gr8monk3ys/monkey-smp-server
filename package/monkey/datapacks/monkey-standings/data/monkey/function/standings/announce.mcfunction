# tools/standings.py close runs this once the week's final table is on the board.
tellraw @a [{"text":"The week's faction standings are in.\n","color":"gold"},{"nbt":"last","storage":"monkey:standings","interpret":true},{"text":"/trigger standings shows the whole board.","color":"gray"}]
