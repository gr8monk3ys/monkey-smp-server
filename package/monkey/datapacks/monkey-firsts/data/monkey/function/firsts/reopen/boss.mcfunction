# Slay a border boss: nobody holds it any more, and the next to do it claims it. Staff: for a first taken
# by a mistake or an exploit (docs/ADMIN.md, "Server Firsts").
# Each border act raises one boss (tools/boss.py); a reopened first waits for the next act's.
data remove storage monkey:firsts held.boss
scoreboard players reset * rf.boss
scoreboard players set #boss rf 0
