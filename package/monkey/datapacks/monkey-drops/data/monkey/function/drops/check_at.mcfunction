$execute unless loaded $(x) 0 $(z) run return run function monkey:drops/wait
$execute in minecraft:overworld positioned $(x) 0 $(z) positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #monkey:drops/ground if block ~ ~ ~ #monkey:drops/open run return run function monkey:drops/found
# Water, a build or anything else: the next spot.
function monkey:drops/next
