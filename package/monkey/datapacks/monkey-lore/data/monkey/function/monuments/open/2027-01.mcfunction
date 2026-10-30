# Staff: opens the January 2027 contest, Ruk's Chair. A new contest starts with no entries.
data modify storage monkey:monuments contest set value {key:"2027-01",month:"January 2027",theme:"Ruk's Chair",about:"a lookout at the top of something tall"}
data remove storage monkey:monuments entries
data modify storage monkey:monuments order set value []
scoreboard players set #open mn 1
tellraw @a ["",{"text":"Monument of the Month, January 2027: ","color":"gold"},{"text":"Ruk's Chair","color":"white"},{"text":" (a lookout at the top of something tall). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #on mn matches 1 run tellraw @s {"text":"Monument of the Month is off: players can't enter until function monkey:monuments/on.","color":"red"}
