schedule function monkey:omens/second 20t replace
# Test play before the launch builds no streak.
execute unless score #launched rw.day matches 1 run scoreboard players reset * om.streak
execute if score #state om matches 0 run return 0
execute if score #arena ev.state matches 1 run return run function monkey:omens/interrupted
execute if score #raid ev.state matches 1.. run return run function monkey:omens/interrupted
execute if score #anarchy ev.state matches 1.. run return run function monkey:omens/interrupted
execute if score #season_locked ev.state matches 1 run return run function monkey:omens/interrupted
execute if score #state om matches 1 run function monkey:omens/blood_moon/second
# A Meteor: announced once the drop counts down (#phase 1); no dry ground at any spot, and it never came.
execute if score #state om matches 2 if score #state dr matches 2.. run scoreboard players set #phase om 1
execute if score #state om matches 2 if score #phase om matches 0 unless score #state dr matches 1.. run function monkey:omens/meteor/failed
execute if score #state om matches 2 if score #phase om matches 1 unless score #state dr matches 1.. run function monkey:omens/end
execute if score #state om matches 3 run function monkey:omens/truce/second
execute if score #state om matches 4 run function monkey:omens/hunted/second
