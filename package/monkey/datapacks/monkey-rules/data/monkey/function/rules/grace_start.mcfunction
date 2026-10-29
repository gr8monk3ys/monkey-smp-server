# Rule 26. Runs as the player; an admin can run it as one: execute as <player> run function monkey:rules/grace_start
execute store result score @s monkey.grace run time query gametime
scoreboard players add @s monkey.grace 3456000
scoreboard players enable @s end_grace
tellraw @s [{"text":"You have 48 hours of PvP grace: other players can't hurt you. ","color":"green"},{"text":"Attacking a player ends it, and so does ","color":"gray"},{"text":"/trigger end_grace","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger end_grace"}},{"text":". Hours count while the server is running.","color":"gray"}]
