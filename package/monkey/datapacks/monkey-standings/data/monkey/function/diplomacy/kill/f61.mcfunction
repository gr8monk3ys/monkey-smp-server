# A player killed a player of faction 61: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f61
function monkey:diplomacy/kill {b:61}
