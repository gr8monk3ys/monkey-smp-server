# Staff: opens the February 2027 contest, The Rope Bridge. A new contest starts with no entries.
data modify storage monkey:monuments contest set value {key:"2027-02",month:"February 2027",theme:"The Rope Bridge",about:"a crossing over something you would rather not fall into"}
data remove storage monkey:monuments entries
data modify storage monkey:monuments order set value []
scoreboard players set #open mn 1
tellraw @a ["",{"text":"Monument of the Month, February 2027: ","color":"gold"},{"text":"The Rope Bridge","color":"white"},{"text":" (a crossing over something you would rather not fall into). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #on mn matches 1 run tellraw @s {"text":"Monument of the Month is off: players can't enter until function monkey:monuments/on.","color":"red"}
