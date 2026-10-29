# A player killed a player of faction 28: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f28
function realms:diplomacy/kill {b:28}
