# Slay the dragon: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
# Players can't bring the dragon back (end crystals are banned), so a reopened dragon stays open until staff
# respawn it by hand. To move it to the right player, reopen it and run claim/dragon as them.
data remove storage monkey:firsts held.dragon
scoreboard players reset * rf.dragon
scoreboard players set #dragon rf 0
