execute if entity @s[tag=ev.arena] run return run tellraw @s {"text":"You're already in. /trigger arena set 2 leaves.","color":"red"}
execute unless entity @s[gamemode=survival] run return run tellraw @s {"text":"Only players in survival can join.","color":"red"}
$execute in minecraft:overworld unless entity @s[x=$(lx),y=$(ly),z=$(lz),distance=..8] run return run tellraw @s {"text":"Come to the arena entrance to join.","color":"red"}
# armor.* takes in the body slot, where a new player's PvP grace item sits (tools/rules.py takes it
# off in the arena and gives it back outside).
execute if items entity @s container.* * run return run tellraw @s {"text":"Empty your inventory, armor and offhand first: you fight with the round's kit, not your gear.","color":"red"}
execute if items entity @s armor.* *[!custom_data~{realms_grace:{}}] run return run tellraw @s {"text":"Empty your inventory, armor and offhand first: you fight with the round's kit, not your gear.","color":"red"}
execute if items entity @s weapon.offhand * run return run tellraw @s {"text":"Empty your inventory, armor and offhand first: you fight with the round's kit, not your gear.","color":"red"}
# Leaving strips kit gear from the ender chest's slots, but not from inside a bundle kept there.
execute if items entity @s enderchest.* #minecraft:bundles run return run tellraw @s {"text":"Take the bundles out of your ender chest first.","color":"red"}
tag @s add ev.arena
scoreboard players operation @s ev.strength = @s Strength_SMP+Strength_Level
scoreboard players set @s Strength_SMP+Strength_Level 3
function realms:events/arena/strength_sync
scoreboard players set @s ev.deaths 0
effect clear @s
gamemode adventure @s
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run tp @s ~ ~ ~
function realms:events/attend
tellraw @s [{"text":"You're in. Your Strength is +3 until you leave, and nothing you get here leaves with you. ","color":"green"},{"text":"[leave]","color":"aqua","click_event":{"action":"run_command","command":"/trigger arena set 2"}}]
