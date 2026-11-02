# How many steps this player has done, into their own rq score (the menu and the reminder show it).
scoreboard players set @s rq 0
execute if score @s rq.done.guide matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.done.home matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.done.faction matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.done.claim matches 1.. run scoreboard players add @s rq 1
execute if score @s rq.done.outpost matches 1.. run scoreboard players add @s rq 1
