scoreboard players reset @s monkey.welcome
dialog show @s monkey:welcome
# A late first join's kit came while they were loading; say so now (tools/catchup.py).
execute if score @s ck.kit matches 1 run function monkey:catchup/note
