# A player killed a player of faction 81: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f81
function monkey:diplomacy/kill {b:81}
