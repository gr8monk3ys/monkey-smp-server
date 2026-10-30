# Staff: opens the March 2027 contest, The Hall. A new contest starts with no entries.
data modify storage monkey:monuments contest set value {key:"2027-03",month:"March 2027",theme:"The Hall",about:"a place where a whole faction can gather"}
data remove storage monkey:monuments entries
data modify storage monkey:monuments order set value []
scoreboard players set #open mn 1
tellraw @a ["",{"text":"Monument of the Month, March 2027: ","color":"gold"},{"text":"The Hall","color":"white"},{"text":" (a place where a whole faction can gather). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #on mn matches 1 run tellraw @s {"text":"Monument of the Month is off: players can't enter until function monkey:monuments/on.","color":"red"}
