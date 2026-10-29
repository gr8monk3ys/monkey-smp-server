# Macro at.o2: every second. Keeps its label up while anyone is near, then counts who is inside.
$execute if entity @a[x=$(nx),y=-64,z=$(nz),dx=128,dy=384,dz=128] run function realms:outposts/o/2/near with storage realms:outposts at.o2
$execute store result score #n op if entity @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24,scores={st.faction=1..}]
# Nobody of a faction inside: an attempt ends.
execute if score #n op matches 0 run return run scoreboard players set #o2 op.prog 0
$execute as @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24,scores={st.faction=1..},limit=1,sort=random] run scoreboard players operation #c op = @s st.faction
scoreboard players set #mixed op 0
$execute as @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24,scores={st.faction=1..}] unless score @s st.faction = #c op run scoreboard players set #mixed op 1
# Two factions inside: contested, and the count waits.
$execute if score #mixed op matches 1 run return run title @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24] actionbar {"text":"The East outpost is contested","color":"red"}
$execute if score #c op = #o2 op.hold run title @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24,scores={st.faction=1..}] actionbar {"text":"Your faction holds the East outpost","color":"green"}
execute if score #c op = #o2 op.hold run return run scoreboard players set #o2 op.prog 0
execute unless score #c op = #o2 op.by run scoreboard players set #o2 op.prog 0
scoreboard players operation #o2 op.by = #c op
scoreboard players add #o2 op.prog 1
execute if score #o2 op.prog matches 1 run function realms:outposts/o/2/attacked
$title @e[type=minecraft:player,gamemode=survival,tag=!ev.arena,x=$(zx),y=$(zy),z=$(zz),dx=24,dy=32,dz=24,scores={st.faction=1..}] actionbar ["",{"text":"Taking the East outpost: ","color":"yellow"},{"score":{"name":"#o2","objective":"op.prog"},"color":"white"},{"text":" of 60 seconds","color":"yellow"}]
execute if score #o2 op.prog matches 60.. run function realms:outposts/o/2/captured
