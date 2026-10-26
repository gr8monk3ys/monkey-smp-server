# rw.midwinter moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.midwinter matches 1.. unless score @s rw.midwinter.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Midwinter Cap","color":"yellow"},{"text":" for coming to Midwinter. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
scoreboard players operation @s rw.midwinter.seen = @s rw.midwinter
