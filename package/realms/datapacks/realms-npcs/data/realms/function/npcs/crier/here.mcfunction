# Run in game by an admin standing where the Town Crier goes, facing the way it should face: it stands
# in the middle of that block. It has no owner, so only admins and creative players can edit it.
execute unless entity @s[type=minecraft:player] run return run say Run this in game, or use /function realms:npcs/crier/place {x:0.5,y:64,z:0.5,yaw:0} from here.
data modify storage realms:npcs place.name set value "crier"
execute store result storage realms:npcs place.yaw float 1 run data get entity @s Rotation[0]
execute align xz positioned ~0.5 ~ ~0.5 summon minecraft:marker run function realms:npcs/spot with storage realms:npcs place
