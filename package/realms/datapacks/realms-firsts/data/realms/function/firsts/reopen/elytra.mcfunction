# Find an elytra: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.elytra
scoreboard players reset * rf.elytra
scoreboard players set #elytra rf 0
