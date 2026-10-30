# As a player: every monument kept, oldest first.
execute unless data storage monkey:monuments hall[0] run return 0
tellraw @s {"text":"The monuments:","color":"gold"}
data modify storage monkey:monuments tmp set from storage monkey:monuments hall
function monkey:monuments/hall_next
