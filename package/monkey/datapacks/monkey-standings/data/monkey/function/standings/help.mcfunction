# Lists the staff commands; click one to put it in the chat box.
tellraw @s {"text":"Standings and bounty commands (docs/ADMIN.md):","color":"gold"}
tellraw @s [{"text":" place","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:standings/place"}},{"text":"  stand where the board goes, at spawn","color":"dark_gray"}]
tellraw @s [{"text":" remove","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:standings/remove"}},{"text":"  next to the board","color":"dark_gray"}]
tellraw @s [{"text":" bounty/post {target:\"Alex\"}","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:standings/bounty/post {target:\"Alex\"}"}},{"text":"  one of the top Strength holders","color":"dark_gray"}]
tellraw @s [{"text":" bounty/claim {hunter:\"Steve\",target:\"Alex\"}","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:standings/bounty/claim {hunter:\"Steve\",target:\"Alex\"}"}},{"text":"  once staff have checked the kill","color":"dark_gray"}]
tellraw @s [{"text":" wanted/on","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:wanted/on"}},{"text":"  players post bounties themselves (docs/SEASONS.md, Switches)","color":"dark_gray"}]
tellraw @s [{"text":" wanted/off","color":"aqua","click_event":{"action":"suggest_command","command":"/function monkey:wanted/off"}},{"text":"  nobody can post or claim one; bounties are kept","color":"dark_gray"}]
