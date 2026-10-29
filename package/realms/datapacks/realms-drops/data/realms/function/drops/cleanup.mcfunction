kill @e[type=minecraft:marker,tag=dr.chest]
kill @e[type=minecraft:text_display,tag=dr.label]
kill @e[type=minecraft:marker,tag=dr.spot]
execute if data storage realms:drops spot.x0 run function realms:drops/release with storage realms:drops spot
schedule clear realms:drops/check
bossbar remove realms:drop
scoreboard players set #state dr 0
scoreboard players set #timer dr 0
scoreboard players set #meteor dr 0
data remove storage realms:drops spot
data remove storage realms:drops spots
