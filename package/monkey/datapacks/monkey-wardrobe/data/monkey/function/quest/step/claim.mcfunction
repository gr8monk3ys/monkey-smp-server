# Claim a chunk: done for good.
scoreboard players set @s rq.claim 1
function monkey:quest/count
execute if score @s rq matches 5.. run return run function monkey:quest/finish
playsound minecraft:entity.experience_orb.pickup player @s ~ ~ ~ 0.6 1
tellraw @s [{"text":"First week: ","color":"gold"},{"text":"Claim a chunk","color":"yellow"},{"text":" done (","color":"gold"},{"score":{"name":"@s","objective":"rq"},"color":"white"},{"text":"/5) ","color":"gold"},{"text":"[Open]","color":"aqua","underlined":true,"click_event":{"action":"run_command","command":"/trigger quest"}}]
