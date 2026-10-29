# Macro {a:3,b:7}: ends a war or a pact between factions 3 and 7 (staff/factions has the numbers), say
# when one broke the rules. Announced as staff's call.
$scoreboard players set #a dp.tmp $(a)
$scoreboard players set #b dp.tmp $(b)
function monkey:diplomacy/pair
function monkey:diplomacy/staff/end_pair with storage monkey:diplomacy pair
