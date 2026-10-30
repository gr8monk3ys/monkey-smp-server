# As a player who found week 5's page for the first time (staff: execute as NAME run function ...).
execute if score @s lr.w5 matches 1 run return 0
scoreboard players set @s lr.w5 1
scoreboard players add @s lr.found 1
function monkey:lore/book/5
playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 1
tellraw @s ["",{"text":"You found page 5 of the Knotkeeper's chronicle: \"The Deep Metal\". ","color":"gold"},{"text":"Pages found: ","color":"gray"},{"score":{"name":"@s","objective":"lr.found"},"color":"white"},{"text":" of 11.","color":"gray"}]
execute if score @s lr.found matches 11.. run function monkey:lore/complete
