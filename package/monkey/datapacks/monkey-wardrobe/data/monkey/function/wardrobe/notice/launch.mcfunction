# rw.launch moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.launch matches 1.. unless score @s rw.launch.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Founder's Circlet","color":"yellow"},{"text":" for playing on launch weekend. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe set 5"}}]
scoreboard players operation @s rw.launch.seen = @s rw.launch
