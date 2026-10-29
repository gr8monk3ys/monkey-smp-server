# A player killed a player of faction 30: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f30
function realms:diplomacy/kill {b:30}
