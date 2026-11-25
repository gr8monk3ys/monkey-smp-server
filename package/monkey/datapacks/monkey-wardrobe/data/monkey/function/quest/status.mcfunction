# One line for the wardrobe's menu (/trigger wardrobe, /trigger challenges): how far a player taking the
# quest is, or that they finished it. Nothing for anyone else, or while the quest is off.
execute unless score #on rq matches 1 run return 0
execute if score @s rq.state matches 2 run return run tellraw @s [{"text":"First week: ","color":"gold"},{"text":"done","color":"green"}]
execute unless score @s rq.state matches 1 run return 0
function monkey:quest/count
tellraw @s [{"text":"First week: ","color":"gold"},{"score":{"name":"@s","objective":"rq"},"color":"white"},{"text":"/5 steps done ","color":"gray"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger quest"}}]
