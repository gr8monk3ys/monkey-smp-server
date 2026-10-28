schedule function realms:omens/second 20t replace
# Test play before the launch builds no streak.
execute unless score #launched rw.day matches 1 run scoreboard players reset * om.streak
execute if score #state om matches 0 run return 0
execute if score #arena ev.state matches 1 run return run function realms:omens/interrupted
execute if score #raid ev.state matches 1.. run return run function realms:omens/interrupted
execute if score #anarchy ev.state matches 1.. run return run function realms:omens/interrupted
execute if score #season_locked ev.state matches 1 run return run function realms:omens/interrupted
execute if score #state om matches 1 run function realms:omens/blood_moon/second
execute if score #state om matches 2 unless score #state dr matches 1.. run function realms:omens/end
execute if score #state om matches 3 run function realms:omens/truce/second
execute if score #state om matches 4 run function realms:omens/hunted/second
