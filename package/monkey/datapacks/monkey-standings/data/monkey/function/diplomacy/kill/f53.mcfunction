# A player killed a player of faction 53: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f53
function monkey:diplomacy/kill {b:53}
