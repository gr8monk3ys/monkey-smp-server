# A player killed a player of faction 76: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f76
function monkey:diplomacy/kill {b:76}
