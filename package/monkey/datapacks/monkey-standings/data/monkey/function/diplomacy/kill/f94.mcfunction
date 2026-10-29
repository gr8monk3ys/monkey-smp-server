# A player killed a player of faction 94: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f94
function monkey:diplomacy/kill {b:94}
