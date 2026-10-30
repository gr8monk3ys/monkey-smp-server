scoreboard players operation #o3 op.hold = #c op
scoreboard players set #o3 op.prog 0
scoreboard players reset #o3 op.by
function monkey:outposts/o/3/label
execute as @e[type=minecraft:text_display,tag=op.l3] run data modify entity @s text set from storage monkey:outposts label.o3
execute store result storage monkey:outposts tmp.c int 1 run scoreboard players get #c op
function monkey:outposts/o/3/taken with storage monkey:outposts tmp
execute if score #open sg matches 1 run function monkey:outposts/o/3/siege with storage monkey:outposts tmp
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.4 1.4
