# Once a wardrobe day, at this player's first second online that day, for their first 7 days
# played: one line with how far they are.
scoreboard players operation @s rq.day = #today rw.day
execute unless score @s rw.days matches ..7 run return 0
tellraw @s ["",{"text":"Your first week: ","color":"gold"},{"score":{"name":"@s","objective":"rq"},"color":"white"},{"text":"/5 steps done. ","color":"gray"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger quest"}}," ",{"text":"[Hide]","color":"gray","click_event":{"action":"run_command","command":"/trigger quest set 2"}}]
