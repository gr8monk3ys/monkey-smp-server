# Get a mace: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.mace
scoreboard players reset * rf.mace
scoreboard players set #mace rf 0
