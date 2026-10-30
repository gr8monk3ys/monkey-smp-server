# As a player who used /trigger camera: 1 toggles, 2 is the menu, 3 and up a warp.
scoreboard players operation #v cm = @s camera
scoreboard players set @s camera 0
execute if score #v cm matches 1 if score @s cm.in matches 1 run return run function monkey:camera/leave
execute if score #v cm matches 1 run return run function monkey:camera/enter
execute unless score @s cm.in matches 1 run return run tellraw @s {"text":"You're not in camera. /trigger camera to go in.","color":"red"}
execute if score #v cm matches 2 run return run function monkey:camera/menu
execute if score #v cm matches 3 run return run function monkey:camera/warp/spawn
execute if score #v cm matches 4 run return run function monkey:camera/warp/board
execute if score #v cm matches 5 run return run function monkey:camera/warp/north
execute if score #v cm matches 6 run return run function monkey:camera/warp/east
execute if score #v cm matches 7 run return run function monkey:camera/warp/south
execute if score #v cm matches 8 run return run function monkey:camera/warp/west
execute if score #v cm matches 9 run return run function monkey:camera/warp/event
