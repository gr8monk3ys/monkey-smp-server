# This player's first login of the day.
scoreboard players add @s rw.days 1
scoreboard players operation @s rw.lastday = #today rw.day
execute if score @s rw.days matches 3 run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Wayfarer","color":"yellow"},{"text":" for 3 days played. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
execute if score @s rw.days matches 15 run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Frostbite","color":"yellow"},{"text":" for 15 days played. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
execute if score @s rw.days matches 30 run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Starfall","color":"yellow"},{"text":" for 30 days played. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
execute if score @s rw.days matches 7 run tellraw @s [{"text":"Unlocked ","color":"gold"},{"text":"Laurel","color":"yellow"},{"text":" for 7 days played. ","color":"gold"},{"text":"[Open the wardrobe]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger wardrobe"}}]
