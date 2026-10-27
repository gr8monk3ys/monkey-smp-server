$execute unless loaded $(x) 0 $(z) run return run function realms:drops/wait
$execute in minecraft:overworld positioned $(x) 0 $(z) positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #realms:drops/ground if block ~ ~ ~ #realms:drops/open run return run function realms:drops/found
# Water, a build or anything else: the next spot.
function realms:drops/next
