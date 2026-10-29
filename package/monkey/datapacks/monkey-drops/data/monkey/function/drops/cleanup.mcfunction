kill @e[type=minecraft:marker,tag=dr.chest]
kill @e[type=minecraft:text_display,tag=dr.label]
kill @e[type=minecraft:marker,tag=dr.spot]
execute if data storage monkey:drops spot.x0 run function monkey:drops/release with storage monkey:drops spot
schedule clear monkey:drops/check
bossbar remove monkey:drop
scoreboard players set #state dr 0
scoreboard players set #timer dr 0
scoreboard players set #meteor dr 0
data remove storage monkey:drops spot
data remove storage monkey:drops spots
