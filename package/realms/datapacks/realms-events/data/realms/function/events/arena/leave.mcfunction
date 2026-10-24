# Out of the arena: nothing comes with you, and your real Strength comes back.
tag @s remove ev.arena
tag @s remove ev.away
clear @s
item replace entity @s player.cursor with minecraft:air
item replace entity @s player.crafting.0 with minecraft:air
item replace entity @s player.crafting.1 with minecraft:air
item replace entity @s player.crafting.2 with minecraft:air
item replace entity @s player.crafting.3 with minecraft:air
effect clear @s
scoreboard players operation @s Strength_SMP+Strength_Level = @s ev.strength
scoreboard players reset @s ev.strength
function realms:events/arena/strength_sync
gamemode survival @s
$execute in minecraft:overworld positioned $(lx) $(ly) $(lz) run tp @s ~ ~ ~
tellraw @s [{"text":"You left the arena. Your Strength is back to +","color":"gray"},{"score":{"name":"@s","objective":"Strength_SMP+Strength_Level"},"color":"white"},{"text":".","color":"gray"}]
