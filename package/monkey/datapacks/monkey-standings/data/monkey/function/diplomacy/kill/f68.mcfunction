# A player killed a player of faction 68: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f68
function monkey:diplomacy/kill {b:68}
