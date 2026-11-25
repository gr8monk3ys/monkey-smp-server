# This player's first login of the day.
scoreboard players add @s rw.days 1
scoreboard players operation @s rw.lastday = #today rw.day
