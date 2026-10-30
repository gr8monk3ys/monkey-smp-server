# rw.s2 moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.s2 matches 1.. unless score @s rw.s2.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Twinmoon","color":"yellow"},{"text":" for playing in Season II. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe set 5"}}]
scoreboard players operation @s rw.s2.seen = @s rw.s2
