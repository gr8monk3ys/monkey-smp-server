# Macro at {act, x, z, hp}: on the surface at the spot (the highest block that stops movement).
$execute in minecraft:overworld unless loaded $(x) 0 $(z) run return run scoreboard players set #wait bs 1
$execute in minecraft:overworld positioned $(x) 0 $(z) align xz positioned ~0.5 ~ ~0.5 positioned over motion_blocking_no_leaves run function monkey:boss/summon
