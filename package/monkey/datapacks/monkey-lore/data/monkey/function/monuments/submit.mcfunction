# As a player standing at their faction's build.
execute unless score @s st.faction matches 1.. run return run tellraw @s {"text":"Only a faction can enter, and the server doesn't know yours yet (the faction list updates every hour).","color":"red"}
execute store result storage monkey:monuments new.f int 1 run scoreboard players get @s st.faction
execute store result storage monkey:monuments new.x int 1 run data get entity @s Pos[0]
execute store result storage monkey:monuments new.y int 1 run data get entity @s Pos[1]
execute store result storage monkey:monuments new.z int 1 run data get entity @s Pos[2]
data modify storage monkey:monuments new.dim set from entity @s Dimension
function monkey:monuments/save with storage monkey:monuments new
