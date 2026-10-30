# As a player who found week 4's page for the first time (staff: execute as NAME run function ...).
execute if score @s lr.w4 matches 1 run return 0
scoreboard players set @s lr.w4 1
scoreboard players add @s lr.found 1
function monkey:lore/book/4
playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 1
tellraw @s ["",{"text":"You found page 4 of the Knotkeeper's chronicle: \"Cloth and Quarrels\". ","color":"gold"},{"text":"Pages found: ","color":"gray"},{"score":{"name":"@s","objective":"lr.found"},"color":"white"},{"text":" of 11.","color":"gray"}]
execute if score @s lr.found matches 11.. run function monkey:lore/complete
