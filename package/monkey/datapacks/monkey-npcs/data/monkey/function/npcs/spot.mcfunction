# Macro {name:guide}, run as a marker by here.mcfunction: places that NPC where the marker stands. The
# marker, not the admin, places it, so the NPC has no owner.
execute store result storage monkey:npcs place.x double 0.01 run data get entity @s Pos[0] 100
execute store result storage monkey:npcs place.y double 0.01 run data get entity @s Pos[1] 100
execute store result storage monkey:npcs place.z double 0.01 run data get entity @s Pos[2] 100
$function monkey:npcs/$(name)/place with storage monkey:npcs place
kill @s[type=minecraft:marker]
