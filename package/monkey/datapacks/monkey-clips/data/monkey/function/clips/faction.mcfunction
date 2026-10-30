# Macro {n}: faction n's name as the board shows it (none if its party is gone).
$execute unless data storage monkey:factions names.f$(n).text run return 0
$data modify storage monkey:clips m.fname set from storage monkey:factions names.f$(n).text
function monkey:clips/join with storage monkey:clips m
