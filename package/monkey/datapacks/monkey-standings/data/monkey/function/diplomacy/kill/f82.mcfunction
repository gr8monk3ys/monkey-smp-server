# A player killed a player of faction 82: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f82
function monkey:diplomacy/kill {b:82}
