# The standings board, if its chunk is loaded; it stands at spawn, so the spawn warp otherwise.
execute unless entity @e[type=minecraft:text_display,tag=st.board] run return run function monkey:camera/warp/spawn
execute at @e[type=minecraft:text_display,tag=st.board,limit=1] run tp @s ^ ^2 ^-6 facing ~ ~2 ~
function monkey:camera/anchor
