# Macro {name, players}: the player, and their faction's name if they have a faction number.
$data modify storage monkey:clips m.players set value "$(players);$(name)"
$execute store result storage monkey:clips m.n int 1 run scoreboard players get $(name) st.faction
$execute if score $(name) st.faction matches 1.. run function monkey:clips/faction with storage monkey:clips m
