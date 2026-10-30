# Macro {faction:N}, staff: names faction N's entry this month's monument. It goes in the hall for good.
execute if data storage monkey:monuments contest{won:1b} run return run tellraw @s {"text":"This contest already has a winner.","color":"red"}
$execute unless data storage monkey:monuments entries.f$(faction) run return run tellraw @s {"text":"Faction $(faction) has no entry in this contest.","color":"red"}
scoreboard players set #n mn 0
execute if data storage monkey:monuments hall[0] store result score #n mn run data get storage monkey:monuments hall
scoreboard players add #n mn 1
$data modify storage monkey:monuments won set from storage monkey:monuments entries.f$(faction)
data modify storage monkey:monuments won.month set from storage monkey:monuments contest.month
data modify storage monkey:monuments won.theme set from storage monkey:monuments contest.theme
execute store result storage monkey:monuments won.n int 1 run scoreboard players get #n mn
execute store result storage monkey:monuments won.season int 1 run scoreboard players get #season rw.day
execute store result storage monkey:monuments won.week int 1 run scoreboard players get #week rc.week
data modify storage monkey:monuments hall append from storage monkey:monuments won
data modify storage monkey:monuments contest.won set value 1b
scoreboard players set #open mn 0
function monkey:monuments/announce with storage monkey:monuments won
