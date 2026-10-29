# Runs as a player who used /trigger outposts.
scoreboard players set @s outposts 0
scoreboard players enable @s outposts
tellraw @s {"text":"Outposts","color":"gold","bold":true}
tellraw @s {"text":"Stand in an outpost's square (about 25 blocks across) with your faction and nobody from another for 60 seconds to take it. Each hour your faction holds one while a player of another faction is online is +1 standings point this week (at most 20). Claims and the rules stay as they are.","color":"gray"}
execute if data storage monkey:outposts at.o1 run function monkey:outposts/o/1/line
execute if data storage monkey:outposts at.o2 run function monkey:outposts/o/2/line
execute if data storage monkey:outposts at.o3 run function monkey:outposts/o/3/line
execute if data storage monkey:outposts at.o4 run function monkey:outposts/o/4/line
execute unless data storage monkey:outposts at.o1 unless data storage monkey:outposts at.o2 unless data storage monkey:outposts at.o3 unless data storage monkey:outposts at.o4 run tellraw @s {"text":"No outposts yet: they are placed within the hour after the launch, and again after each border act.","color":"gray"}
execute unless score @s st.faction matches 1.. run return run tellraw @s {"text":"You're in no faction the server knows yet, so you can't take one. Make or join a party (/oparties); the server picks it up within the hour.","color":"gray"}
execute store result storage monkey:outposts me.f int 1 run scoreboard players get @s st.faction
function monkey:outposts/mine with storage monkey:outposts me
