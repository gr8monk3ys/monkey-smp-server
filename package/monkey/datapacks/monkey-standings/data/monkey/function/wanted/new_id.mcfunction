# The first second a player is seen: their number, for the menu's buttons.
scoreboard players add #next wt.id 1
scoreboard players operation @s wt.id = #next wt.id
scoreboard players add @s wt.gen 0
scoreboard players add @s st.wanted 0
