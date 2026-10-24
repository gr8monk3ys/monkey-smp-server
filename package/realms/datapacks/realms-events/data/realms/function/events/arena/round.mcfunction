# Between rounds: clear the floor (items go every tick anyway; this takes arrows and tridents too).
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=#minecraft:arrows,distance=..$(size)]
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=minecraft:trident,distance=..$(size)]
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=minecraft:item,distance=..$(size)]
