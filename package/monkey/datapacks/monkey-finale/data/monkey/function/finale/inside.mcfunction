# Macro edge {x, z, r}: as a player outside the border: to a safe spot inside it (around the border's
# centre, not the monument: no free trip to the hold), told why.
$execute in minecraft:overworld run spreadplayers $(x) $(z) 0 $(r) false @s
tellraw @s {"text":"You were outside the finale's border, so you were moved inside it.","color":"gold"}
