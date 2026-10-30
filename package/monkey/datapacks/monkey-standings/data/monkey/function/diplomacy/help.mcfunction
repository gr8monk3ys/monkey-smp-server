# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"War and pacts, staff commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" staff/factions","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:diplomacy/staff/factions"}},{"text":"  every faction's number and name","color":"dark_gray"}]
tellraw @s [{"text":" staff/end {a:3,b:7}","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:diplomacy/staff/end {a:3,b:7}"}},{"text":"  ends a war or pact between two factions, announced","color":"dark_gray"}]
tellraw @s [{"text":" staff/wars_on","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:diplomacy/staff/wars_on"}},{"text":"  7-day wars on (off by default: wars run until Sunday's close)","color":"dark_gray"}]
tellraw @s [{"text":" staff/wars_off","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:diplomacy/staff/wars_off"}},{"text":"  back to wars until Sunday's close; running 7-day wars go on","color":"dark_gray"}]
tellraw @s [{"text":" staff/wars","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:diplomacy/staff/wars"}},{"text":"  the 7-day wars running and the clock","color":"dark_gray"}]
