# A function run by the server runs at the world spawn, so ~ ~ is spawn.
execute in minecraft:overworld run worldborder center ~ ~
execute in minecraft:overworld run worldborder set 2500
# Since 26.3 each dimension has its own border (the Nether's no longer follows the overworld's), so
# give the Nether the one it used to have: the same area at its 1:8 scale.
execute summon minecraft:marker run function monkey:rules/nether_border
scoreboard players set #border monkey.rules 1
