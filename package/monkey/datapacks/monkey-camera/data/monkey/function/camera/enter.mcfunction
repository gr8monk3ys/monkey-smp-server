# As an approved creator going into camera: the rules first (docs/ADMIN.md, "Creator camera").
execute unless score #on cm matches 1 run return run tellraw @s {"text":"The creator camera is off.","color":"red"}
execute unless score @s cm.ok matches 1 run return run tellraw @s {"text":"The camera is for creators staff have approved.","color":"red"}
execute unless score #open cm matches 1.. run return run tellraw @s {"text":"The camera only works in a camera window staff open for an event.","color":"red"}
execute if score @s st.faction matches 1.. run return run tellraw @s {"text":"Faction members can't use the camera: it would show your faction where everyone is.","color":"red"}
execute if entity @s[tag=ev.arena] run return run tellraw @s {"text":"Not from the event arena.","color":"red"}
execute if score @s cm.wait matches 1.. run return run tellraw @s {"text":"You were hurt in the last 15 seconds. Try again in a moment.","color":"red"}
execute if entity @s[gamemode=spectator] run return run tellraw @s {"text":"You're in spectator already.","color":"red"}
# Where to come back to, and in which game mode.
execute store result score @s cm.x run data get entity @s Pos[0] 100
execute store result score @s cm.y run data get entity @s Pos[1] 100
execute store result score @s cm.z run data get entity @s Pos[2] 100
execute at @s if dimension minecraft:overworld run scoreboard players set @s cm.dim 0
execute at @s if dimension minecraft:the_nether run scoreboard players set @s cm.dim 1
execute at @s if dimension minecraft:the_end run scoreboard players set @s cm.dim 2
execute if entity @s[gamemode=survival] run scoreboard players set @s cm.mode 0
execute if entity @s[gamemode=creative] run scoreboard players set @s cm.mode 1
execute if entity @s[gamemode=adventure] run scoreboard players set @s cm.mode 2
execute if entity @s[gamemode=spectator] run scoreboard players set @s cm.mode 3
scoreboard players set @s cm.in 1
gamemode spectator @s
function monkey:camera/anchor
tellraw @a ["",{"selector":"@s","color":"white"},{"text":" is filming with the creator camera (spectator) for this event.","color":"gray"}]
tellraw @s {"text":"Camera rules: no coordinates, bases or player positions shared with anyone, on stream or off; the camera stays near its warp; staff can take it back.","color":"gray"}
function monkey:camera/menu
