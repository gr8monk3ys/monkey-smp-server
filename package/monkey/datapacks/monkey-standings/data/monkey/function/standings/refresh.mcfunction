# Runs as a board display that is behind.
data modify entity @s text set from storage monkey:standings board
scoreboard players operation @s st.ver = #board st.ver
