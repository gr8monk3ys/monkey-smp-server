# rw.quest moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.quest matches 1.. unless score @s rw.quest.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Pathfinder","color":"yellow"},{"text":" for finishing your first week. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
scoreboard players operation @s rw.quest.seen = @s rw.quest
