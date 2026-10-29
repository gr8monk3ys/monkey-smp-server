# Ends whatever omen is on, putting back what it changed.
execute if score #state om matches 1 run function monkey:omens/blood_moon/calm
execute if score #state om matches 3 run function monkey:omens/truce/restore
execute if score #state om matches 4 run function monkey:omens/hunted/over
scoreboard players reset * om.hunt
bossbar remove monkey:omen
scoreboard players set #state om 0
scoreboard players set #phase om 0
scoreboard players set #timer om 0
data remove storage monkey:omens target
data remove storage monkey:omens hunt
data remove storage monkey:omens spots
