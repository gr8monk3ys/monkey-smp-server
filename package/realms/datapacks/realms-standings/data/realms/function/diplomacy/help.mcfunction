# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"War and pacts, staff commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" staff/factions","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:diplomacy/staff/factions"}},{"text":"  every faction's number and name","color":"dark_gray"}]
tellraw @s [{"text":" staff/end {a:3,b:7}","color":"aqua","click_event":{"action":"suggest_command","command":"/function realms:diplomacy/staff/end {a:3,b:7}"}},{"text":"  ends a war or pact between two factions, announced","color":"dark_gray"}]
