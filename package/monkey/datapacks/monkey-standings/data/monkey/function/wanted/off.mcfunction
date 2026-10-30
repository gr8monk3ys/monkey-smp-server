# Staff: turns it off. Nobody can post or claim, and the Most Wanted leaves the board now; bounties
# already posted are kept for when it is on again.
scoreboard players set #on wt 0
data modify storage monkey:standings wanted set value {text:""}
function monkey:standings/publish
tellraw @s {"text":"The wanted board is off.","color":"yellow"}
