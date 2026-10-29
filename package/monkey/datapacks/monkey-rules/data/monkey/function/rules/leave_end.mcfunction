# Runs as a player in the End while it's closed; the position is still the world spawn's x and z.
execute in minecraft:overworld positioned over motion_blocking_no_leaves run tp @s ~ ~ ~
tellraw @s [{"text":"The End is closed for now. ","color":"red"},{"text":"The owners will announce when it opens.","color":"gray"}]
