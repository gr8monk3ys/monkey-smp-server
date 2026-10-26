$scoreboard players set #min dr $(players)
tellraw @s [{"text":"Weeknight drops now need ","color":"green"},{"score":{"name":"#min","objective":"dr"},"color":"aqua"},{"text":" survival players online (and that many more for each extra chest).","color":"green"}]
