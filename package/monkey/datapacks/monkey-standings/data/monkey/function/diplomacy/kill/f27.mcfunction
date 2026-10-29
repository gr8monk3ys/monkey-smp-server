# A player killed a player of faction 27: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f27
function monkey:diplomacy/kill {b:27}
