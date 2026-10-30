# Staff: opens the December 2026 contest, The Long Night. A new contest starts with no entries.
data modify storage monkey:monuments contest set value {key:"2026-12",month:"December 2026",theme:"The Long Night",about:"a light against the Midwinter dark"}
data remove storage monkey:monuments entries
data modify storage monkey:monuments order set value []
scoreboard players set #open mn 1
tellraw @a ["",{"text":"Monument of the Month, December 2026: ","color":"gold"},{"text":"The Long Night","color":"white"},{"text":" (a light against the Midwinter dark). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #on mn matches 1 run tellraw @s {"text":"Monument of the Month is off: players can't enter until function monkey:monuments/on.","color":"red"}
