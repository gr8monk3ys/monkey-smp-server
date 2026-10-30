scoreboard players operation #o2 op.hold = #c op
scoreboard players set #o2 op.prog 0
scoreboard players reset #o2 op.by
function monkey:outposts/o/2/label
execute as @e[type=minecraft:text_display,tag=op.l2] run data modify entity @s text set from storage monkey:outposts label.o2
execute store result storage monkey:outposts tmp.c int 1 run scoreboard players get #c op
function monkey:outposts/o/2/taken with storage monkey:outposts tmp
execute if score #open sg matches 1 run function monkey:outposts/o/2/siege with storage monkey:outposts tmp
# A clip marker as the taker nearest the outpost's label (in the middle; no capture while contested).
execute at @e[type=minecraft:text_display,tag=op.l2,limit=1] as @a[distance=..25,limit=1,sort=nearest,scores={st.faction=1..}] at @s run function monkey:clips/mark {kind:"outpost",title:"The East outpost is taken",other:""}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.4 1.4
