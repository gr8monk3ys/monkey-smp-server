# Light a beacon: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.beacon
scoreboard players reset * rf.beacon
scoreboard players set #beacon rf 0
