# A player killed a player of faction 50: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f50
function realms:diplomacy/kill {b:50}
