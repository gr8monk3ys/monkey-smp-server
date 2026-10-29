# Run at the candidate's surface: it is dry land, so the outpost stands here.
summon minecraft:marker ~ ~ ~ {Tags:["op.y"]}
execute store result storage realms:outposts cand.y int 1 run data get entity @e[type=minecraft:marker,tag=op.y,limit=1] Pos[1]
kill @e[type=minecraft:marker,tag=op.y]
# The square's corner (zx, zy, zz), the near box's (nx, nz), the far corner (ex, ez) and the label's
# height (ly).
execute store result score #x op run data get storage realms:outposts cand.x
execute store result score #y op run data get storage realms:outposts cand.y
execute store result score #z op run data get storage realms:outposts cand.z
execute store result storage realms:outposts cand.zx int 1 run scoreboard players remove #x op 12
execute store result storage realms:outposts cand.ex int 1 run scoreboard players add #x op 24
execute store result storage realms:outposts cand.nx int 1 run scoreboard players remove #x op 76
execute store result storage realms:outposts cand.zz int 1 run scoreboard players remove #z op 12
execute store result storage realms:outposts cand.ez int 1 run scoreboard players add #z op 24
execute store result storage realms:outposts cand.nz int 1 run scoreboard players remove #z op 76
execute store result storage realms:outposts cand.zy int 1 run scoreboard players remove #y op 8
execute store result storage realms:outposts cand.ly int 1 run scoreboard players add #y op 11
function realms:outposts/settle with storage realms:outposts cand
function realms:outposts/skip
