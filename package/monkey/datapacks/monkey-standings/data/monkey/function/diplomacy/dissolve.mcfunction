# Macro {a, b}: tools/standings.py sends this when one of the two factions' parties is gone: their war
# or pact ends, and the other gets its pact back.
$scoreboard players set #a dp.tmp $(a)
$scoreboard players set #b dp.tmp $(b)
function monkey:diplomacy/pair
function monkey:diplomacy/dissolve_pair with storage monkey:diplomacy pair
