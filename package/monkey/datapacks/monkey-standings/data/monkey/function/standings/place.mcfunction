# Run by staff standing where the board goes (spawn). It turns to face whoever reads it.
summon minecraft:text_display ~ ~1.5 ~ {Tags:["st.board"],billboard:"vertical",alignment:"left",line_width:400}
tellraw @s {"text":"Standings board placed. To move it, run standings/remove next to it and place it again.","color":"green"}
