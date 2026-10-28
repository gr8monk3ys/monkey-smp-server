# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"Omen commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" start/blood_moon","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/start/blood_moon"}},{"text":"  at the next nightfall (not on Peaceful)","color":"dark_gray"}]
tellraw @s [{"text":" start/truce","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/start/truce"}},{"text":"  no PvP for 60 minutes","color":"dark_gray"}]
tellraw @s [{"text":" hunt {name:\"Alex\"}","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/hunt {name:\"Alex\"}"}},{"text":"  hunt Alex for 30 minutes (online, in survival)","color":"dark_gray"}]
tellraw @s [{"text":" stop","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/stop"}},{"text":"  ends the omen that is on","color":"dark_gray"}]
tellraw @s [{"text":" status","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/status"}},{"text":"  what's on, and the settings","color":"dark_gray"}]
tellraw @s [{"text":" min {players:4}","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/min {players:4}"}},{"text":"  survival players needed for an evening's omen","color":"dark_gray"}]
tellraw @s [{"text":" off","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/off"}},{"text":"  no automatic omens until on","color":"dark_gray"}]
tellraw @s [{"text":" on","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:omens/on"}},{"text":"  automatic omens again","color":"dark_gray"}]
tellraw @s {"text":" A Meteor by hand: /function realms:drops/start","color":"dark_gray"}
