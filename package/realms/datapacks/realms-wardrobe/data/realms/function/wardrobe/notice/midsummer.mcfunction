# rw.midsummer moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.midsummer matches 1.. unless score @s rw.midsummer.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Solstice","color":"yellow"},{"text":" for coming to Midsummer. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
scoreboard players operation @s rw.midsummer.seen = @s rw.midsummer
