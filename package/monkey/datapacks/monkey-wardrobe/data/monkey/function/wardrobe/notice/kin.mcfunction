# rw.kin moved (the store, staff or an event set it): say which skins it just unlocked.
execute if score @s rw.kin matches 1.. unless score @s rw.kin.seen matches 1.. run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Kindred Band","color":"yellow"},{"text":" for a referral. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe set 5"}}]
scoreboard players operation @s rw.kin.seen = @s rw.kin
