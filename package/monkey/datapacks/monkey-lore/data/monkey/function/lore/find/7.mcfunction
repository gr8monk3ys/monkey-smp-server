# As a player who found week 7's page for the first time (staff: execute as NAME run function ...).
execute if score @s lr.w7 matches 1 run return 0
scoreboard players set @s lr.w7 1
scoreboard players add @s lr.found 1
function monkey:lore/book/7
playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 1
tellraw @s ["",{"text":"You found page 7 of the Knotkeeper's chronicle: \"The Second Loosening\". ","color":"gold"},{"text":"Pages found: ","color":"gray"},{"score":{"name":"@s","objective":"lr.found"},"color":"white"},{"text":" of 11.","color":"gray"}]
execute if score @s lr.found matches 11.. run function monkey:lore/complete
