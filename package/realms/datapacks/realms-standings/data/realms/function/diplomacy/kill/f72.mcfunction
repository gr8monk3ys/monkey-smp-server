# A player killed a player of faction 72: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f72
function realms:diplomacy/kill {b:72}
