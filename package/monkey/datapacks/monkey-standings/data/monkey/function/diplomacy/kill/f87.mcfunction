# A player killed a player of faction 87: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f87
function monkey:diplomacy/kill {b:87}
