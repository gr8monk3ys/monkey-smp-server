# Filled now rather than given a loot table to roll when opened: Loot Restock (2.8.0) remembers every
# chest that is opened with a loot table and refills it a week later, which would make a drop's spot
# a weekly supply drop.
setblock ~ ~ ~ minecraft:chest{CustomName:"Supply drop"}
loot insert ~ ~ ~ loot realms:drops/supply
summon minecraft:marker ~ ~ ~ {Tags:["dr.chest"]}
particle minecraft:end_rod ~ ~1 ~ 0.3 1.5 0.3 0.05 40 force
