# This player's first time online this week (or the week just turned): show them the three.
scoreboard players operation @s rc.seen = #week rc.week
tellraw @s ["",{"text":"Weekly challenges","color":"gold"},{"text":"  new every Monday (Pacific)  ","color":"gray"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger challenges"}}]
function monkey:challenges/lines
