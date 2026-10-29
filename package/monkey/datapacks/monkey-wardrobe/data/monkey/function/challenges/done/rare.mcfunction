# Visit 2 rare structures: done for this week. One more toward the challenge skins (rw.challenges).
scoreboard players set @s rc.rare.done 1
scoreboard players add @s rw.challenges 1
playsound minecraft:entity.player.levelup player @s ~ ~ ~ 0.6 1.2
tellraw @s [{"text":"Challenge done: ","color":"gold"},{"text":"Visit 2 rare structures","color":"yellow"},{"text":" (","color":"gold"},{"score":{"name":"@s","objective":"rw.challenges"},"color":"yellow"},{"text":" done in all) ","color":"gold"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger challenges"}}]
