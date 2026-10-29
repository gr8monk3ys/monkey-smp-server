# A player killed a player of faction 16: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f16
function monkey:diplomacy/kill {b:16}
