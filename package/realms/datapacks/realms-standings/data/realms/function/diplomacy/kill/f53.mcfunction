# A player killed a player of faction 53: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f53
function realms:diplomacy/kill {b:53}
