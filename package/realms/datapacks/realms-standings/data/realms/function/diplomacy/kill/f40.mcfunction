# A player killed a player of faction 40: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f40
function realms:diplomacy/kill {b:40}
