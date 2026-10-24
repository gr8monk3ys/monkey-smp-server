# Out of the arena: nothing comes with you, and your real Strength comes back.
tag @s remove ev.arena
tag @s remove ev.away
clear @s
item replace entity @s player.cursor with minecraft:air
item replace entity @s player.crafting.0 with minecraft:air
item replace entity @s player.crafting.1 with minecraft:air
item replace entity @s player.crafting.2 with minecraft:air
item replace entity @s player.crafting.3 with minecraft:air
execute if items entity @s enderchest.0 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.0 with minecraft:air
execute if items entity @s enderchest.1 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.1 with minecraft:air
execute if items entity @s enderchest.2 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.2 with minecraft:air
execute if items entity @s enderchest.3 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.3 with minecraft:air
execute if items entity @s enderchest.4 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.4 with minecraft:air
execute if items entity @s enderchest.5 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.5 with minecraft:air
execute if items entity @s enderchest.6 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.6 with minecraft:air
execute if items entity @s enderchest.7 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.7 with minecraft:air
execute if items entity @s enderchest.8 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.8 with minecraft:air
execute if items entity @s enderchest.9 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.9 with minecraft:air
execute if items entity @s enderchest.10 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.10 with minecraft:air
execute if items entity @s enderchest.11 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.11 with minecraft:air
execute if items entity @s enderchest.12 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.12 with minecraft:air
execute if items entity @s enderchest.13 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.13 with minecraft:air
execute if items entity @s enderchest.14 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.14 with minecraft:air
execute if items entity @s enderchest.15 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.15 with minecraft:air
execute if items entity @s enderchest.16 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.16 with minecraft:air
execute if items entity @s enderchest.17 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.17 with minecraft:air
execute if items entity @s enderchest.18 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.18 with minecraft:air
execute if items entity @s enderchest.19 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.19 with minecraft:air
execute if items entity @s enderchest.20 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.20 with minecraft:air
execute if items entity @s enderchest.21 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.21 with minecraft:air
execute if items entity @s enderchest.22 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.22 with minecraft:air
execute if items entity @s enderchest.23 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.23 with minecraft:air
execute if items entity @s enderchest.24 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.24 with minecraft:air
execute if items entity @s enderchest.25 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.25 with minecraft:air
execute if items entity @s enderchest.26 *[custom_data~{realms_kit:{}}] run item replace entity @s enderchest.26 with minecraft:air
effect clear @s
scoreboard players operation @s Strength_SMP+Strength_Level = @s ev.strength
scoreboard players reset @s ev.strength
function realms:events/arena/strength_sync
gamemode survival @s
$execute in minecraft:overworld positioned $(lx) $(ly) $(lz) run tp @s ~ ~ ~
tellraw @s [{"text":"You left the arena. Your Strength is back to +","color":"gray"},{"score":{"name":"@s","objective":"Strength_SMP+Strength_Level"},"color":"white"},{"text":".","color":"gray"}]
