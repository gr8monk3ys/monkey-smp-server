# Every second, as a creator in camera: out if any rule no longer holds (the leash is every tick).
execute unless score #on cm matches 1 run return run function monkey:camera/leave
execute unless score #open cm matches 1.. run return run function monkey:camera/leave
execute unless score @s cm.ok matches 1 run return run function monkey:camera/leave
execute if score @s st.faction matches 1.. run return run function monkey:camera/leave
execute unless entity @s[gamemode=spectator] run return run function monkey:camera/leave
