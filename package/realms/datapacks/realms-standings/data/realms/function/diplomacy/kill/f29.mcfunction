# A player killed a player of faction 29: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f29
function realms:diplomacy/kill {b:29}
