# A player killed a player of faction 57: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f57
function monkey:diplomacy/kill {b:57}
