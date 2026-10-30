# Every step done: the quest is over, and the Pathfinder blade is theirs (the wardrobe announces it).
scoreboard players set @s rq.state 2
scoreboard players set @s rw.quest 1
playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.8 1
tellraw @s [{"text":"Your first week is done. ","color":"gold"},{"text":"Every step, in your first days. Welcome to Monkey SMP.","color":"yellow"}]
