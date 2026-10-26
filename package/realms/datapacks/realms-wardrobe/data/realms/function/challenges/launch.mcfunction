# Run by realms:rules/launch: this week's progress starts from zero. At Season I's first launch, what test
# play earned goes too: challenges done, and Founder's Circlet from a window staff opened to try it.
# #launched makes that once only, so a launch run again by mistake wipes nothing earned since; later
# seasons keep the counts they carried.
function realms:challenges/restart
execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run scoreboard players reset * rw.challenges
execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run scoreboard players reset * rw.challenges.seen
execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run scoreboard players reset * rw.launch
execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run scoreboard players reset * rw.launch.seen
execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run scoreboard players reset * rw.launchtime
scoreboard players set #launched rw.day 1
