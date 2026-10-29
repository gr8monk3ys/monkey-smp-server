# A player killed a player of faction 88: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f88
function realms:diplomacy/kill {b:88}
