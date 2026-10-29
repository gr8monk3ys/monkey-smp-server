# A player killed a player of faction 38: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f38
function monkey:diplomacy/kill {b:38}
