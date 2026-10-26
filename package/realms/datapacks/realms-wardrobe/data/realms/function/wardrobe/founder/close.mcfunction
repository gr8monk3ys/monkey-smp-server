# Shuts the window: by itself when the time is up, from founder/sync at the end of Sunday, or staff.
scoreboard players set #founder.open rw.day 0
scoreboard players set #founder.auto rw.day 0
tellraw @a [{"text":"The launch weekend is over. ","color":"gold"},{"text":"Founder's Circlet stays with everyone who earned it.","color":"yellow"}]
