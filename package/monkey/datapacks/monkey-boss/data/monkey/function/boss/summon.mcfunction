# Health: 150 + 40 for each survival player online, from 200 to 1000.
execute store result score #hp bs if entity @a[gamemode=survival]
scoreboard players set #k bs 40
scoreboard players operation #hp bs *= #k bs
scoreboard players add #hp bs 150
execute if score #hp bs matches ..199 run scoreboard players set #hp bs 200
execute if score #hp bs matches 1001.. run scoreboard players set #hp bs 1000
execute store result storage monkey:boss at.hp int 1 run scoreboard players get #hp bs
summon minecraft:wither_skeleton ~ ~ ~ {Tags:["monkey.boss","bs.new"],PersistenceRequired:1b,CanPickUpLoot:0b,CustomNameVisible:1b,CustomName:{"text":"The Edgewalker","color":"dark_red","bold":true},equipment:{mainhand:{id:"minecraft:diamond_sword",count:1},head:{id:"minecraft:diamond_helmet",count:1},chest:{id:"minecraft:diamond_chestplate",count:1}},drop_chances:{mainhand:0.0f,head:0.0f,chest:0.0f}}
execute as @e[type=minecraft:wither_skeleton,tag=bs.new] run function monkey:boss/setup
scoreboard players set #left bs 5400
scoreboard players set #state bs 2
execute store result bossbar monkey:boss max run scoreboard players get #hp bs
execute store result bossbar monkey:boss value run scoreboard players get #hp bs
bossbar set monkey:boss visible true
function monkey:boss/risen with storage monkey:boss at
playsound minecraft:entity.wither.spawn master @a ~ ~ ~ 1000 0.6
