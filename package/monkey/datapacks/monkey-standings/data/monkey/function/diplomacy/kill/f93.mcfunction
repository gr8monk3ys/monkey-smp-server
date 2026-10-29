# A player killed a player of faction 93: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f93
function monkey:diplomacy/kill {b:93}
