# A player with no registered team: a team of one, the next number from SOLO_FROM.
scoreboard players operation @s st.team = #next fn
scoreboard players add #next fn 1
