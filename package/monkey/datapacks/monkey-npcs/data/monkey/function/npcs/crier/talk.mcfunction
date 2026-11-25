# Run by the Town Crier's FancyNpcs right-click action, from the server console, as the player who clicked:
#   execute as {player} run function monkey:npcs/crier/talk
# (docs/ADMIN.md, "Spawn NPCs"). The console's permission lets it show a dialog.
execute unless entity @s[type=minecraft:player] run return run say Run it as a player: execute as <player> run function monkey:npcs/crier/talk
# This week's, by the challenges' week number; anyone without one gets the general one.
execute if score @s rc.seen matches 0 run return run dialog show @s monkey:npcs/crier/week0
execute if score @s rc.seen matches 1 run return run dialog show @s monkey:npcs/crier/week1
execute if score @s rc.seen matches 2 run return run dialog show @s monkey:npcs/crier/week2
execute if score @s rc.seen matches 3 run return run dialog show @s monkey:npcs/crier/week3
execute if score @s rc.seen matches 4 run return run dialog show @s monkey:npcs/crier/week4
execute if score @s rc.seen matches 5 run return run dialog show @s monkey:npcs/crier/week5
execute if score @s rc.seen matches 6 run return run dialog show @s monkey:npcs/crier/week6
execute if score @s rc.seen matches 7 run return run dialog show @s monkey:npcs/crier/week7
execute if score @s rc.seen matches 8 run return run dialog show @s monkey:npcs/crier/week8
execute if score @s rc.seen matches 9 run return run dialog show @s monkey:npcs/crier/week9
dialog show @s monkey:npcs/crier/other
