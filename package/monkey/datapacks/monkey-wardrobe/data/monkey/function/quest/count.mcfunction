# How many steps this player has done, into their own rq score (the menu and the reminder show it).
scoreboard players set @s rq 0
execute if score @s rq.guide matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.home matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.faction matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.claim matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.outpost matches 1.. run scoreboard players add @s rq 1
