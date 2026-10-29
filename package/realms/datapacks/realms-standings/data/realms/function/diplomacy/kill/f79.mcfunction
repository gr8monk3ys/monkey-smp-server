# A player killed a player of faction 79: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f79
function realms:diplomacy/kill {b:79}
