# A player killed a player of faction 96: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f96
function monkey:diplomacy/kill {b:96}
