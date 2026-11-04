##by Tschipcraft

# Schedule for next tick
schedule function dynamiclights:internal/main 1t

# Detect explosions: every tick, as a light block stops explosion damage
execute as @e[type=minecraft:tnt,limit=10] at @s run function dynamiclights:internal/explosion_detection/tnt

# Light every other tick, unless a fuse is ending
scoreboard players add $pass ts.dl.settings 1
execute if score $pass ts.dl.settings matches 2.. run scoreboard players set $pass ts.dl.settings 0
execute if score $global ts.dl.tnt.fuse matches 1 run scoreboard players set $pass ts.dl.settings 0

# Tag old lights
execute if score $pass ts.dl.settings matches 0 run tag @e[type=minecraft:marker,tag=ts.dl.light] add ts.dl.remove

# Core
execute if score $pass ts.dl.settings matches 0 if score $enable ts.dl.settings matches 1..2 unless score $global ts.dl.tnt.fuse matches 1 as @a[gamemode=!spectator,tag=!smithed.strict,tag=!global.ignore,tag=!global.ignore.gui,tag=!ts.dl.ignore] at @s run function dynamiclights:internal/main_exec_pass

execute if score $pass ts.dl.settings matches 0 if score $enable ts.dl.settings matches 1..2 unless score $global ts.dl.tnt.fuse matches 1 as @e[type=!minecraft:player,type=!#dynamiclights:dyn_ignore,tag=!smithed.strict,tag=!global.ignore,tag=!global.ignore.gui,tag=!ts.dl.ignore,tag=!ts.sa.hidden,limit=750] at @s run function dynamiclights:internal/main_exec

# Clear old lights
execute if score $pass ts.dl.settings matches 0 as @e[type=minecraft:marker,tag=ts.dl.remove] at @s run function dynamiclights:internal/remove_light
