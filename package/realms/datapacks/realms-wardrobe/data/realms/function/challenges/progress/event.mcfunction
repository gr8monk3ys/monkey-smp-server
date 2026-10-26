# Come to an event: this week's progress into rc.faction, run as each player once a second while it is on.
scoreboard players set @s rc.faction 0
execute if score @s ev.seen >= #firstevent rc.week run scoreboard players set @s rc.faction 1
execute if score @s rc.faction matches 1.. unless score @s rc.event.done matches 1 run function realms:challenges/done/event
