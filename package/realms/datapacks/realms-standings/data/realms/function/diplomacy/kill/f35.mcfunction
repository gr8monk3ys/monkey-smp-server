# A player killed a player of faction 35: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f35
function realms:diplomacy/kill {b:35}
