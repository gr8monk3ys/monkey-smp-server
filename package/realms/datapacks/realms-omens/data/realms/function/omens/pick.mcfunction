# Tries the omens in the order sent, first to last; returns 1 for the first that starts.
execute unless data storage realms:omens order[0] run return 0
data modify storage realms:omens next set value {}
data modify storage realms:omens next.id set from storage realms:omens order[0]
data remove storage realms:omens order[0]
execute store result score #r om run function realms:omens/begin with storage realms:omens next
execute if score #r om matches 1 run return 1
return run function realms:omens/pick
