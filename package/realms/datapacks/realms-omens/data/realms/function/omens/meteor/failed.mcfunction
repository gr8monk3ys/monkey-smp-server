# The drop found no dry ground at any spot, so the Meteor never came: tonight's omen isn't used up, and
# the next omen in the order is tried now.
scoreboard players set #state om 0
scoreboard players set #phase om 0
execute store result score #r om run function realms:omens/pick
execute if score #r om matches 1 run return run function realms:omens/record with storage realms:omens tonight
function realms:omens/unrecord with storage realms:omens tonight
scoreboard players operation #night om = #prev om
