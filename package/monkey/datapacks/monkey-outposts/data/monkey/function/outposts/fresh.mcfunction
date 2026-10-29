# A new border ring: every outpost goes, and its holder with it (hours already earned stay).
execute if score #ring op matches 1.. run tellraw @a ["",{"text":"Outposts: ","color":"gold","bold":true},{"text":"the border has moved, and the outposts move out to the new land. Their spots follow in chat.","color":"yellow"}]
data remove storage monkey:outposts at
scoreboard players reset #o1 op.hold
scoreboard players reset #o1 op.by
scoreboard players reset #o1 op.prog
scoreboard players reset #o1 op.id
scoreboard players reset #o2 op.hold
scoreboard players reset #o2 op.by
scoreboard players reset #o2 op.prog
scoreboard players reset #o2 op.id
scoreboard players reset #o3 op.hold
scoreboard players reset #o3 op.by
scoreboard players reset #o3 op.prog
scoreboard players reset #o3 op.id
scoreboard players reset #o4 op.hold
scoreboard players reset #o4 op.by
scoreboard players reset #o4 op.prog
scoreboard players reset #o4 op.id
scoreboard players operation #ring op = #want op
