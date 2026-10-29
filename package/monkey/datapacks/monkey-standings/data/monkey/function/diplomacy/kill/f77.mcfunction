# A player killed a player of faction 77: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f77
function monkey:diplomacy/kill {b:77}
