schedule function realms:standings/second 20t replace
scoreboard players enable @a standings
# A board whose chunk was unloaded when the standings changed catches up once it is loaded again.
execute as @e[type=minecraft:text_display,tag=st.board] unless score @s st.ver = #board st.ver run function realms:standings/refresh
