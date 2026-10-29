# A player killed a player of faction 61: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f61
function realms:diplomacy/kill {b:61}
