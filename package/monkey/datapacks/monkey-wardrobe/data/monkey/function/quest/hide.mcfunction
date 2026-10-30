# Hidden: no more reminders, and no steps checked. /trigger quest still shows it, with a way back.
scoreboard players set @s rq.state 3
tellraw @s [{"text":"First-week quest hidden. ","color":"gray"},{"text":"/trigger quest brings it back.","color":"dark_gray"}]
