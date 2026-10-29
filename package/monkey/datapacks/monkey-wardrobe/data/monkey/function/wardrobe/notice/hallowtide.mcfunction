# rw.hallowtide moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.hallowtide matches 1.. unless score @s rw.hallowtide.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Gravelight","color":"yellow"},{"text":" for coming to Hallowtide. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
scoreboard players operation @s rw.hallowtide.seen = @s rw.hallowtide
