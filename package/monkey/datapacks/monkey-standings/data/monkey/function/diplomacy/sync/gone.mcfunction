# Missing on two runs in a row: the faction is gone (its war and pacts were dissolved just before). Its
# name is kept apart, for the Sunday post's lines about its week (report()).
$data modify storage monkey:diplomacy gone.f$(n) set from storage monkey:factions names.f$(n)
$data remove storage monkey:factions names.f$(n)
$data remove storage monkey:diplomacy missing.f$(n)
