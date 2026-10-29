# A player killed a player of faction 74: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f74
function realms:diplomacy/kill {b:74}
