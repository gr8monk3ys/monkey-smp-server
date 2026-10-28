# A player killed a player of faction 77: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f77
function realms:diplomacy/kill {b:77}
