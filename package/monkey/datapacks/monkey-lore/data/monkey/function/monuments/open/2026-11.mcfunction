# Staff: opens the November 2026 contest, The Gate. A new contest starts with no entries.
data modify storage monkey:monuments contest set value {key:"2026-11",month:"November 2026",theme:"The Gate",about:"an entrance worth walking through"}
data remove storage monkey:monuments entries
data modify storage monkey:monuments order set value []
scoreboard players set #open mn 1
tellraw @a ["",{"text":"Monument of the Month, November 2026: ","color":"gold"},{"text":"The Gate","color":"white"},{"text":" (an entrance worth walking through). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #on mn matches 1 run tellraw @s {"text":"Monument of the Month is off: players can't enter until function monkey:monuments/on.","color":"red"}
