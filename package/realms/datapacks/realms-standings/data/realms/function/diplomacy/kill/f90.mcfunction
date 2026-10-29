# A player killed a player of faction 90: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f90
function realms:diplomacy/kill {b:90}
