scoreboard players operation #o1 op.hold = #c op
scoreboard players set #o1 op.prog 0
scoreboard players reset #o1 op.by
function monkey:outposts/o/1/label
execute as @e[type=minecraft:text_display,tag=op.l1] run data modify entity @s text set from storage monkey:outposts label.o1
execute store result storage monkey:outposts tmp.c int 1 run scoreboard players get #c op
function monkey:outposts/o/1/taken with storage monkey:outposts tmp
# A clip marker as the taker nearest the outpost's label (in the middle; no capture while contested).
execute at @e[type=minecraft:text_display,tag=op.l1,limit=1] as @a[distance=..25,limit=1,sort=nearest,scores={st.faction=1..}] at @s run function monkey:clips/mark {kind:"outpost",title:"The North outpost is taken",other:""}
execute as @a at @s run playsound minecraft:event.raid.horn master @s ~ ~ ~ 0.4 1.4
