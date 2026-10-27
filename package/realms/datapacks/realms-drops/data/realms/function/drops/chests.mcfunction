# Run at the drop's middle.
execute if score #chests dr matches 1.. positioned ~0 ~ ~0 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #realms:drops/ground if block ~ ~ ~ #realms:drops/open run function realms:drops/place
execute if score #chests dr matches 2.. positioned ~3 ~ ~2 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #realms:drops/ground if block ~ ~ ~ #realms:drops/open run function realms:drops/place
execute if score #chests dr matches 3.. positioned ~-3 ~ ~2 positioned over motion_blocking_no_leaves if block ~ ~-1 ~ #realms:drops/ground if block ~ ~ ~ #realms:drops/open run function realms:drops/place
