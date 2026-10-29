# A player killed a player of faction 34: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f34
function monkey:diplomacy/kill {b:34}
