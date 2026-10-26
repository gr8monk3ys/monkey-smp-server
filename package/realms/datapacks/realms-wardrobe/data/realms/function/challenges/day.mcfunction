# This player's first time online in a wardrobe day, this week.
scoreboard players add @s rc.days 1
scoreboard players operation @s rc.lastday = #today rw.day
