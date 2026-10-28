# Returns 1 when the Meteor starts: the drop checks the ground at the spots sent and counts down.
execute unless data storage realms:omens spots[0] run return 0
data modify storage realms:drops spots set from storage realms:omens spots
data remove storage realms:omens spots
execute store result score #r om run function realms:drops/meteor
execute unless score #r om matches 1 run return 0
scoreboard players set #state om 2
return 1
