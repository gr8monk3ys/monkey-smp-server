# Macro {hunter:"Steve",target:"Alex"}, once staff have checked the kill: a bounty for Steve's
# faction this week (+5 standings points), and the Bounty Hunter title if Steve shows no
# other (a supporter color or title is never taken away for it). Run by staff in game, so the notes
# reach them; over RCON only the chat line shows.
tag @s add st.staff
$scoreboard players add $(hunter) st.bounty 1
$tellraw @a [{"text":"Bounty claimed: ","color":"gold"},{"text":"$(hunter)","color":"white"},{"text":" took the bounty on ","color":"gray"},{"text":"$(target)","color":"white"},{"text":". +5 standings points for their faction this week, and the Bounty Hunter title.","color":"gray"}]
$execute as $(hunter) if entity @s[team=] run team join bounty_hunter @s
$execute as $(hunter) unless entity @s[team=bounty_hunter] run tellraw @a[tag=st.staff] {"text":"$(hunter) shows another title, so it stays. If they would rather show Bounty Hunter: team join bounty_hunter $(hunter)","color":"yellow"}
$execute unless entity $(hunter) run tellraw @a[tag=st.staff] {"text":"$(hunter) is offline: the points count. For the title, when they are on and show no other: team join bounty_hunter $(hunter)","color":"yellow"}
tag @s remove st.staff
