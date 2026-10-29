# A player killed a player of faction 11: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f11
function realms:diplomacy/kill {b:11}
