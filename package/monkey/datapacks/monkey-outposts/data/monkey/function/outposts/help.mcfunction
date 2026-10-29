# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"Outpost commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" status","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:outposts/status"}},{"text":"  where each outpost is, who holds it, the settings","color":"dark_gray"}]
tellraw @s [{"text":" release {i:1}","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:outposts/release {i:1}"}},{"text":"  frees outpost 1 (1 North, 2 East, 3 South, 4 West), announced","color":"dark_gray"}]
tellraw @s [{"text":" off","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:outposts/off"}},{"text":"  no captures, no hours and no new spots until on","color":"dark_gray"}]
tellraw @s [{"text":" on","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:outposts/on"}},{"text":"  outposts again","color":"dark_gray"}]
