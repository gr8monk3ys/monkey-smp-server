# Find a diamond: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.diamond
scoreboard players reset * rf.diamond
scoreboard players set #diamond rf 0
