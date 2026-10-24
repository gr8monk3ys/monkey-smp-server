# Macro {id:"red",points:30,why:"Build Battle, 1st"}.
$scoreboard players add $(id) ev.cup $(points)
$tellraw @a [{"text":"Season Cup: ","color":"gold"},{"text":"+$(points) to $(id)","color":"white"},{"text":" ($(why)). Now ","color":"gray"},{"score":{"name":"$(id)","objective":"ev.cup"},"color":"white"},{"text":".","color":"gray"}]
