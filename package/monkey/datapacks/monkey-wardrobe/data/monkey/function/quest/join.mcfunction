# The first second this player is seen after the launch (with the quest on). New to the server: no play
# carried from an earlier season (rw.playbase) and at most 3 days played. Anyone else is
# marked as not taking part, and never hears of it.
scoreboard players set @s rq.state 0
execute if score @s rw.playbase matches 1.. run return 0
execute unless score @s rw.days matches ..3 run return 0
scoreboard players set @s rq.state 1
scoreboard players operation @s rq.day = #today rw.day
function monkey:quest/count
tellraw @s ["",{"text":"Your first week: ","color":"gold"},{"text":"5 steps to find your feet, and the Pathfinder blade at the end. ","color":"yellow"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger quest"}}," ",{"text":"[Hide]","color":"gray","click_event":{"action":"run_command","command":"/trigger quest set 2"}}]
