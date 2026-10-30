# The quest's menu. Only a player taking part (or who hid it, or finished it) sees the steps.
tellraw @s ["",{"text":"\nYour first week","color":"gold","bold":true},{"text":"  five steps, and a skin at the end","color":"gray"}]
execute unless score #on rq matches 1 run return run tellraw @s {"text":" The first-week quest is off for now.","color":"gray"}
execute unless score #launched rw.day matches 1 run return run tellraw @s {"text":" It starts when the season launches.","color":"gray"}
execute unless score @s rq.state matches 1.. run return run tellraw @s {"text":" It's for players new this season. Your challenges: /trigger challenges","color":"gray"}
function monkey:quest/count
function monkey:quest/line/guide
function monkey:quest/line/home
function monkey:quest/line/faction
function monkey:quest/line/claim
function monkey:quest/line/outpost
execute if score @s rq.state matches 2 run return run tellraw @s [" ",{"text":"Done: the Pathfinder blade is in your wardrobe. ","color":"green"},{"text":"[Wardrobe]","color":"aqua","click_event":{"action":"run_command","command":"/trigger wardrobe set 1"}}]
execute if score @s rq.state matches 3 run return run tellraw @s [" ",{"text":"Hidden: no reminders. ","color":"gray"},{"text":"[Show it again]","color":"aqua","click_event":{"action":"run_command","command":"/trigger quest set 3"}}]
tellraw @s [" ",{"text":"Reward: the Pathfinder blade. ","color":"gray"},{"score":{"name":"@s","objective":"rq"},"color":"white"},{"text":"/5 done  ","color":"gray"},{"text":"[Hide]","color":"gray","click_event":{"action":"run_command","command":"/trigger quest set 2"}}]
