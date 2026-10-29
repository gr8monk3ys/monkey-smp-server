# A player killed a player of faction 24: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f24
function monkey:diplomacy/kill {b:24}
