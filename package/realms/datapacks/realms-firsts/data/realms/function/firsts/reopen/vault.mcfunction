# Open a trial vault: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
data remove storage realms:firsts held.vault
scoreboard players reset * rf.vault
scoreboard players set #vault rf 0
