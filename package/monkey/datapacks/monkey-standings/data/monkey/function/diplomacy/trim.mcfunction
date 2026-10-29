# Removes the log's entries numbered up to #trim dp.tmp (the log is in number order).
execute unless data storage monkey:diplomacy log[0] run return 0
execute store result score #n dp.tmp run data get storage monkey:diplomacy log[0].n
execute if score #n dp.tmp > #trim dp.tmp run return 0
data remove storage monkey:diplomacy log[0]
function monkey:diplomacy/trim
