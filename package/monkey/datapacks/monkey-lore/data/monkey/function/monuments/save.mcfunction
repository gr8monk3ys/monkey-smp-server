# Macro {f,x,y,z,dim}, as the player: keeps the faction's entry, with its name as the board shows it.
$execute store success score #had mn if data storage monkey:monuments entries.f$(f)
$data modify storage monkey:monuments entries.f$(f) set from storage monkey:monuments new
$data modify storage monkey:monuments entries.f$(f).faction set from storage monkey:factions names.f$(f)
$execute unless data storage monkey:monuments entries.f$(f).faction run data modify storage monkey:monuments entries.f$(f).faction set value {text:"Faction $(f)"}
$execute if score #had mn matches 0 run data modify storage monkey:monuments order append value {f:$(f)}
$tellraw @s [{"text":"Your faction's monument entry is at $(x) $(y) $(z). ","color":"green"},{"text":"Run it again somewhere else to move it. Post a screenshot in its thread on the Discord when voting opens.","color":"gray"}]
$execute if score #had mn matches 0 run tellraw @a ["",{"nbt":"entries.f$(f).faction","storage":"monkey:monuments","interpret":true,"color":"gold"},{"text":" entered this month's monument contest.","color":"yellow"}]
