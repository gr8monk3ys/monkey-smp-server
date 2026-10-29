# Each second, as a hostile mob near a player: faster and tougher for 3 seconds (so it wears
# off soon after dawn, loaded or not), and marked with this moon's number for the bonus drop.
scoreboard players operation @s om.blood = #moon om
effect give @s minecraft:speed 3 0 true
effect give @s minecraft:resistance 3 0 true
