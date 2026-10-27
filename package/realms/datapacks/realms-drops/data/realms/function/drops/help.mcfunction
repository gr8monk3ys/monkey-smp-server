# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"Supply drop commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" start {x:0,z:0}","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/start {x:0,z:0}"}},{"text":"  a drop at those coordinates, now (any number online)","color":"dark_gray"}]
tellraw @s [{"text":" here","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/here"}},{"text":"  a drop where you stand, now","color":"dark_gray"}]
tellraw @s [{"text":" stop","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/stop"}},{"text":"  ends the drop now; its chests go","color":"dark_gray"}]
tellraw @s [{"text":" status","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/status"}},{"text":"  what's on, and the settings","color":"dark_gray"}]
tellraw @s [{"text":" min {players:4}","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/min {players:4}"}},{"text":"  survival players needed for the weeknight drop","color":"dark_gray"}]
tellraw @s [{"text":" off","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/off"}},{"text":"  no weeknight drops until on","color":"dark_gray"}]
tellraw @s [{"text":" on","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:drops/on"}},{"text":"  weeknight drops again","color":"dark_gray"}]
