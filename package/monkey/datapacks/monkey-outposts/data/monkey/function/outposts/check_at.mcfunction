$execute in minecraft:overworld unless loaded $(x) 0 $(z) run return run function monkey:outposts/wait
$execute in minecraft:overworld positioned $(x) 0 $(z) align xz positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #monkey:outposts/ground run return run function monkey:outposts/found
# Water, a build or anything else: the next candidate.
function monkey:outposts/skip
