# Lists the staff commands; click one to put it in the chat box.
tellraw @s ["",{"text":"Siege window commands (docs/ADMIN.md):","color":"gold"}]
tellraw @s ["",{"text":" staff/on","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:sieges/staff/on"}},{"text":"  siege windows on (off by default)","color":"dark_gray"}]
tellraw @s ["",{"text":" staff/off","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:sieges/staff/off"}},{"text":"  siege windows off; an open one closes now","color":"dark_gray"}]
tellraw @s ["",{"text":" staff/status","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:sieges/staff/status"}},{"text":"  on or off, open or not, the next window","color":"dark_gray"}]
