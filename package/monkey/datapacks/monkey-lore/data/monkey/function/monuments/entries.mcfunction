# Staff: this contest's entries, by faction number (the number win takes).
execute unless data storage monkey:monuments order[0] run return run tellraw @s {"text":"No entries.","color":"gray"}
data modify storage monkey:monuments tmp set from storage monkey:monuments order
function monkey:monuments/entries_next
