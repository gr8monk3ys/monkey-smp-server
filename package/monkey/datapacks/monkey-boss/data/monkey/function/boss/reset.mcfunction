# Staff, test servers only: forget every act, so the next act raises a boss again.
function monkey:boss/off
scoreboard players set #act bs 0
data remove storage monkey:boss acts
