# Runs as a player who used /trigger wanted: 1 to 9 opens the menu, a player's wt.id posts a bounty.
scoreboard players operation #v wt = @s wanted
scoreboard players set @s wanted 0
scoreboard players enable @s wanted
execute unless score #on wt matches 1 run return run tellraw @s {"text":"The wanted board is off for now.","color":"red"}
execute if score #v wt matches ..9 run return run function monkey:wanted/menu
execute unless score #launched rw.day matches 1 run return run tellraw @s {"text":"Bounties open when the season launches.","color":"red"}
function monkey:wanted/post
tag @a remove wt.target
