# A player with no registered team: a team of one, the next number from SOLO_FROM (none past MAX_TEAMS).
execute unless score #next fn matches ..999 run return 0
scoreboard players operation @s st.team = #next fn
scoreboard players add #next fn 1
