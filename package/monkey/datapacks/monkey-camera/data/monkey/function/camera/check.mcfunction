# Every second, as a creator in camera: out if any rule no longer holds, else the leash.
execute unless score #on cm matches 1 run return run function monkey:camera/leave
execute unless score #open cm matches 1.. run return run function monkey:camera/leave
execute unless score @s cm.ok matches 1 run return run function monkey:camera/leave
execute if score @s st.faction matches 1.. run return run function monkey:camera/leave
execute unless entity @s[gamemode=spectator] run return run function monkey:camera/leave
execute at @s unless dimension minecraft:overworld run return run function monkey:camera/snap
execute store result score #x cm run data get entity @s Pos[0]
execute store result score #z cm run data get entity @s Pos[2]
scoreboard players operation #x cm -= @s cm.ax
scoreboard players operation #z cm -= @s cm.az
execute unless score #x cm matches -160..160 run return run function monkey:camera/snap
execute unless score #z cm matches -160..160 run return run function monkey:camera/snap
