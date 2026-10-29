# A player killed a player of faction 45: take the advancement back so the next kill fires it too.
advancement revoke @s only monkey:diplomacy/kill/f45
function monkey:diplomacy/kill {b:45}
