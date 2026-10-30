# Macro {name}: approve a creator for the camera (staff only). Not a faction member.
$execute if score $(name) st.faction matches 1.. run return run tellraw @s {"text":"$(name) is in a faction: the camera is only for players in none.","color":"red"}
$scoreboard players set $(name) cm.ok 1
$tellraw @s [{"text":"$(name) can use /trigger camera in camera windows. Tell them the rules: ","color":"green"},{"text":"Camera rules: stream it with a delay of 5 minutes or more (rule 10: nobody snipes from your stream); no coordinates, bases or player positions shared with anyone, on stream or off; the camera stays near its warp; staff can take it back.","color":"gray"}]
