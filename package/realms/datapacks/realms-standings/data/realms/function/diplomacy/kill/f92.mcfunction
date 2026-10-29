# A player killed a player of faction 92: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f92
function realms:diplomacy/kill {b:92}
