# Shuts the window: by itself when the time is up, from founder/sync at the end of Sunday, or staff.
scoreboard players set #founder.open rw.day 0
scoreboard players set #founder.auto rw.day 0
tellraw @a [{"text":"The launch weekend is over. ","color":"gold"},{"text":"Everyone who played it stays a launch-weekend founder.","color":"yellow"}]
