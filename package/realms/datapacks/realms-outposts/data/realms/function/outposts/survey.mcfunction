# deploy/realms-outposts.sh: macro {ring, fresh}, after putting the spots in storage cands
# ([{i, x, z}], the first for each outpost first). fresh 1: a new border, so every outpost starts over;
# 0: only the outposts named get a spot (holders keep them). Returns why it didn't start (SURVEY_CODES).
execute unless score #auto op matches 1 run return 10
execute if score #busy op matches 1 run return 11
execute unless score #launched rw.day matches 1 run return 12
execute if score #season_locked ev.state matches 1 run return 15
$scoreboard players set #fresh op $(fresh)
$scoreboard players set #want op $(ring)
execute if score #fresh op matches 1 if score #want op = #ring op run return 13
execute if score #fresh op matches 0 unless score #want op = #ring op run return 14
execute unless data storage realms:outposts cands[0] run return 16
scoreboard players set #busy op 1
scoreboard players set #d1 op 0
scoreboard players set #d2 op 0
scoreboard players set #d3 op 0
scoreboard players set #d4 op 0
execute if score #fresh op matches 1 run function realms:outposts/fresh
function realms:outposts/next
return 1
