# A player killed a player of faction 16: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f16
function realms:diplomacy/kill {b:16}
