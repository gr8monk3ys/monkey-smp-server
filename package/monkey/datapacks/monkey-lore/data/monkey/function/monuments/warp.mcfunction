# Macro {n:N}, as a player: to monument N in the hall (a spawn NPC's button runs it; never on its own).
$execute unless data storage monkey:monuments hall[{n:$(n)}] run return run tellraw @s {"text":"There is no monument $(n).","color":"red"}
$function monkey:monuments/go with storage monkey:monuments hall[{n:$(n)}]
