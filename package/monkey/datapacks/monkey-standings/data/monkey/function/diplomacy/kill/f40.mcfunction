# A player killed a player of faction 40: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f40
function monkey:diplomacy/kill {b:40}
