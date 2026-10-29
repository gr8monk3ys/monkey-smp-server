# Find a bastion: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.bastion
scoreboard players reset * rf.bastion
scoreboard players set #bastion rf 0
