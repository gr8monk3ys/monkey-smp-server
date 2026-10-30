# Every tick, as a creator in camera: in the Overworld, within LEASH blocks of the last warp.
execute at @s unless dimension minecraft:overworld run return run function monkey:camera/snap
execute store result score #x cm run data get entity @s Pos[0]
execute store result score #z cm run data get entity @s Pos[2]
scoreboard players operation #x cm -= @s cm.ax
scoreboard players operation #z cm -= @s cm.az
execute unless score #x cm matches -64..64 run return run function monkey:camera/snap
execute unless score #z cm matches -64..64 run return run function monkey:camera/snap
