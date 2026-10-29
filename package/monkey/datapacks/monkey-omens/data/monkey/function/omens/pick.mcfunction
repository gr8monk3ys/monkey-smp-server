# Tries the omens in the order sent, first to last; returns 1 for the first that starts.
execute unless data storage monkey:omens order[0] run return 0
data modify storage monkey:omens next set value {}
data modify storage monkey:omens next.id set from storage monkey:omens order[0]
data remove storage monkey:omens order[0]
execute store result score #r om run function monkey:omens/begin with storage monkey:omens next
execute if score #r om matches 1 run return 1
return run function monkey:omens/pick
