# Runs as a player who just used /trigger quest: 1 the menu, 2 hide it, 3 show it again.
execute if score @s quest matches 2 if score @s rq.state matches 1 run function monkey:quest/hide
execute if score @s quest matches 3 if score @s rq.state matches 3 run scoreboard players set @s rq.state 1
execute unless score @s quest matches 2 run function monkey:quest/menu
scoreboard players set @s quest 0
scoreboard players enable @s quest
