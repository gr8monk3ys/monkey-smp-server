# A player killed a player of faction 93: take the advancement back so the next kill fires it too.
advancement revoke @s only realms:diplomacy/kill/f93
function realms:diplomacy/kill {b:93}
