# Defeat 15 fortress mobs: done for this week. One more toward the challenge skins (rw.challenges).
scoreboard players set @s rc.fortress.done 1
scoreboard players add @s rw.challenges 1
playsound minecraft:entity.player.levelup player @s ~ ~ ~ 0.6 1.2
tellraw @s [{"text":"Challenge done: ","color":"gold"},{"text":"Defeat 15 fortress mobs","color":"yellow"},{"text":" (","color":"gold"},{"score":{"name":"@s","objective":"rw.challenges"},"color":"yellow"},{"text":" done in all) ","color":"gold"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger challenges"}}]
