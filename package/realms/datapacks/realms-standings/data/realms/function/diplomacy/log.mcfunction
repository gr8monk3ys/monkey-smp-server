# Macro {kind, a, b}: one declaration, numbered, for the Sunday Discord post (tools/diplomacy.py report).
scoreboard players add #seq dp.state 1
$data modify storage realms:diplomacy log append value {kind:"$(kind)",a:$(a),b:$(b)}
execute store result storage realms:diplomacy log[-1].n int 1 run scoreboard players get #seq dp.state
