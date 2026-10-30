# Staff: no more entries. Voting is on the Discord; then name the winner with win {faction:N}.
execute unless score #open mn matches 1 run return run tellraw @s {"text":"No contest is open.","color":"red"}
scoreboard players set #open mn 0
tellraw @a ["",{"text":"Monument entries are closed: ","color":"gold"},{"text":"vote for your favourite on the Discord.","color":"gray"}]
function monkey:monuments/entries
