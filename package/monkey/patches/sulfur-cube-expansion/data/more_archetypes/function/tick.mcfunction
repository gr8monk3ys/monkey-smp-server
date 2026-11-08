# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"): upstream ran about 45 world-wide @e scans
# every tick, 33 of them @e[type=sulfur_cube] for one archetype each. The server's passes (middle block) now visit
# each Herobrine mannequin, each sulfur cube and each dropped Boombox once, and run this function again as that
# entity. The other blocks are upstream's lines for one entity, in upstream's order. Every entity stops at the end
# of its own block, and the server stops after its passes.

#THE JUKEBOX ITEM THAT DROPS WHEN TRACK IS STOPPED (run as one dropped Boombox)
execute if entity @s[type=minecraft:item] at @s run stopsound @a[distance=..300] record
execute if entity @s[type=minecraft:item] run return run kill @s

#hero brian (run as one mannequin, at the server's position like upstream, so @p is the same player)
execute if entity @s[tag=temp_mannequin] run rotate @s facing entity @p
execute if entity @s[tag=temp_mannequin] if data entity @s CustomName run tag @s remove temp_mannequin
execute if entity @s[tag=temp_mannequin,scores={despawn_timer=5}] at @s if entity @a[distance=..3] run swing @s
execute if entity @s[tag=temp_mannequin,scores={despawn_timer=5}] at @s run execute as @a[distance=..3] run damage @s 2 minecraft:starve
execute if entity @s[tag=temp_mannequin,scores={despawn_timer=1..}] run scoreboard players remove @s despawn_timer 1
#execute as @e[tag=temp_mannequin,scores={despawn_timer=4..5}] run data modify entity @s Motion[1] set value 10.0d
execute if entity @s[tag=temp_mannequin,scores={despawn_timer=..1}] at @s run tp ~ ~1000 ~
execute if entity @s[tag=temp_mannequin,scores={despawn_timer=..0}] run return run kill @s
execute if entity @s unless entity @s[type=minecraft:sulfur_cube] run return 0

# (run by the server every tick)
#DYNAMIC LIGHT/REDSTONE
execute unless entity @s as @e[tag=sulfur_cube_dinamic_light] at @s run function more_archetypes:luminous_marker_tick
execute unless entity @s as @e[tag=sulfur_cube_dinamic_charge] at @s run function more_archetypes:charged_marker_tick
#hero brian
execute unless entity @s as @e[tag=temp_mannequin] run function more_archetypes:tick
#each sulfur cube's archetype
execute unless entity @s as @e[type=minecraft:sulfur_cube] at @s run function more_archetypes:tick
#THE JUKEBOX ITEM THAT DROPS WHEN TRACK IS STOPPED (the id check first, so only jukeboxes have their NBT read)
execute unless entity @s as @e[type=item] if items entity @s contents minecraft:jukebox if entity @s[nbt={Item:{id:"minecraft:jukebox",components:{"minecraft:custom_name":"§k§lBoombox"}}}] run function more_archetypes:tick
execute unless entity @s[type=minecraft:sulfur_cube] run return 0

# (run as one sulfur cube, at the cube)
#FRAGILE
execute if entity @s[name="§lGlass Piece"] run return run kill @s

#remove bugged blockstates
execute as @e[type=item,distance=..1] run data remove entity @s Item.components."minecraft:block_state"

#ARCHETYPES-=-=-=-=-=-=-=-=-

#HOT AIR
execute if predicate more_archetypes:hot_air unless entity @s[y=190,dy=1000] run effect give @s minecraft:levitation 1 0 true

#STICKY
execute unless block ~ ~1 ~ #minecraft:air if predicate more_archetypes:sticky run effect give @s minecraft:levitation 1 0 true
#EXTRA STICKY
execute unless block ~ ~1 ~ #minecraft:air if predicate more_archetypes:extra_sticky run effect give @s minecraft:levitation 1 0 true

#SHULKER
execute if predicate more_archetypes:shulker run effect give @e[distance=0.1..1.3] minecraft:levitation 10 0 false
#HEALING
execute if predicate more_archetypes:healing run effect give @e[distance=0.1..1.3] minecraft:regeneration 1 2 false
#BOOSTER
execute if predicate more_archetypes:booster run effect give @e[distance=0.1..1.3] minecraft:jump_boost 1 4 false

#CREEPY
execute if predicate more_archetypes:creepy run function more_archetypes:creepy_tick

#POTENT
execute if predicate more_archetypes:potent run effect give @e[distance=0.1..8] minecraft:nausea 5 0 false
execute if predicate more_archetypes:potent run particle minecraft:noxious_gas ~ ~ ~ 4 4 4 0.01 1 force

#ANVIL
execute if predicate more_archetypes:anvil run function more_archetypes:anvil_tick

#OVEN
execute if predicate more_archetypes:oven run function more_archetypes:oven_tick

#SONIC
execute if predicate more_archetypes:sonic if entity @e[distance=0.1..1.1,type=!#more_archetypes:sonic_blacklist] run function more_archetypes:sonic_tick

#BARBED + BLOCKSTATE CHANGE
execute if predicate more_archetypes:barbed run function more_archetypes:barbed_tick

#FRAGILES + BLOCKSTATE CHANGE
execute if predicate more_archetypes:fragile run function more_archetypes:fragile_tick
execute if predicate more_archetypes:fragile_panes run function more_archetypes:multiple_sides_extend

#BEDS,ANCHORS BLOCKSTATE CHANGE
execute if predicate more_archetypes:small_explosive run function more_archetypes:small_explosive_tick
execute if predicate more_archetypes:big_explosive run data modify entity @s equipment.body.components."minecraft:block_state".charges set value "4"
#DRIED GHAST BLOCKSTATE CHANGE
execute if predicate more_archetypes:dried_ghast run data modify entity @s equipment.body.components."minecraft:block_state".facing set value "south"
execute if predicate more_archetypes:dried_ghast run data modify entity @s equipment.body.components."minecraft:block_state".hydration set value "2"
#PROPELLER BLOCKSTATE CHANGE
execute if predicate more_archetypes:propeller run function more_archetypes:propeller_tick

#=-=-=-=-=-=-=-=-=-=-
#CHARGED - DYNAMIC REDSTONE
execute if predicate more_archetypes:charged run function more_archetypes:charged_tick

#LUMINOUS - DYNAMIC LIGHTS
execute if predicate more_archetypes:luminous_torch run function more_archetypes:luminous_torch_tick
execute if predicate more_archetypes:luminous_r_torch run function more_archetypes:luminous_r_torch_tick
execute if predicate more_archetypes:luminous_lantern run function more_archetypes:luminous_lantern_tick

#BOOMBOX
execute if predicate more_archetypes:boombox_running run function more_archetypes:boombox_playing
execute if predicate more_archetypes:boombox run function more_archetypes:boombox_play

#RESIZES
execute if predicate more_archetypes:bigger run function more_archetypes:sulfur_cube_bigger
execute if predicate more_archetypes:smaller run function more_archetypes:sulfur_cube_smaller

#CREATIVE EXCLUSIVE
execute if predicate more_archetypes:cheaty run fill ~ ~ ~ ~ ~ ~ minecraft:light replace #minecraft:air
execute if predicate more_archetypes:cheaty run execute as @e[distance=..8] unless predicate more_archetypes:cheaty run effect give @s minecraft:glowing 1 0 false
