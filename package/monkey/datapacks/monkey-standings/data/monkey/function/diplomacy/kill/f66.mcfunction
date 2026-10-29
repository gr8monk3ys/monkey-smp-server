# A player killed a player of faction 66: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f66
function monkey:diplomacy/kill {b:66}
