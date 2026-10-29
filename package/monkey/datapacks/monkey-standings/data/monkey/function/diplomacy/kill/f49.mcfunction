# A player killed a player of faction 49: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f49
function monkey:diplomacy/kill {b:49}
