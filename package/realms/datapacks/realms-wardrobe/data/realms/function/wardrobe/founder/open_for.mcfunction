# Macro {hours:N}, staff only: opens the window (or keeps it open) for N hours of game time from now.
# The wall clock no longer moves its end; founder/close shuts it early. Season I only.
execute unless score #season rw.day matches 1 run return run tellraw @s {"text":"Founder's Circlet is only for Season I's launch weekend.","color":"red"}
$scoreboard players set #founder.until rw.day $(hours)
scoreboard players operation #founder.until rw.day *= #hour rw.const
execute store result score #founder.now rw.day run time query gametime
scoreboard players operation #founder.until rw.day += #founder.now rw.day
scoreboard players set #founder.open rw.day 1
scoreboard players set #founder.auto rw.day 0
$tellraw @a [{"text":"Launch weekend: ","color":"gold"},{"text":"Founder's Circlet is open for $(hours) more hours. Play 10 minutes to keep it.","color":"yellow"}]
