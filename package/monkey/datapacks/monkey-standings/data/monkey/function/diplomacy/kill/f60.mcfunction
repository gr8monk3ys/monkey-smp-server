# A player killed a player of faction 60: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f60
function monkey:diplomacy/kill {b:60}
