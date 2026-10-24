# Macro {size:N}: the arena's radius around the pit. Items there are removed every tick, and a
# player in the arena who ends up farther away (a teleport) is taken out.
$data modify storage realms:events arena.size set value $(size)
tellraw @s {"text":"Arena size set.","color":"green"}
