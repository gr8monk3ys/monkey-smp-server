# Run at the drop's middle.
execute if score #chests dr matches 1.. positioned ~0 ~ ~0 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #monkey:drops/ground if block ~ ~ ~ #monkey:drops/open run function monkey:drops/place
execute if score #chests dr matches 2.. positioned ~3 ~ ~2 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #monkey:drops/ground if block ~ ~ ~ #monkey:drops/open run function monkey:drops/place
execute if score #chests dr matches 3.. positioned ~-3 ~ ~2 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #monkey:drops/ground if block ~ ~ ~ #monkey:drops/open run function monkey:drops/place
