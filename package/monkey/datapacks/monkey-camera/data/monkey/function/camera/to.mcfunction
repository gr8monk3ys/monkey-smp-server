# Macro {x, z}: above the ground there. A height check needs the chunk loaded and silently does nothing
# if it isn't, so the plain teleport comes first: the warp happens either way, and the leash's middle
# (camera/anchor) is never where the creator was standing.
$execute in minecraft:overworld run tp @s $(x) 120 $(z)
$execute in minecraft:overworld positioned $(x) 0 $(z) positioned over motion_blocking run tp @s ~ ~20 ~
