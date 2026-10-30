# /trigger lore: this week's line again, and the pages this player has found.
scoreboard players set @s lore 0
execute if score #told lr matches 1..11 run function monkey:lore/greet
execute unless score #told lr matches 1..11 run tellraw @s {"text":"The Town Crier has no page of the Knotkeeper's chronicle yet: the first is announced in week 1.","color":"gray"}
execute unless score @s lr.found matches 1.. run scoreboard players set @s lr.found 0
tellraw @s ["",{"text":"Pages you have found: ","color":"gold"},{"score":{"name":"@s","objective":"lr.found"},"color":"white"},{"text":" of 11. Find them all for the Knotkeeper title.","color":"gray"}]
