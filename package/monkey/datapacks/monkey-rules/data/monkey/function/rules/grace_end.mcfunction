# Rule 26. Runs as the player: when the grace runs out, they attack a player or /trigger end_grace.
# An admin can end one: execute as <player> run function monkey:rules/grace_end
scoreboard players reset @s monkey.grace
scoreboard players reset @s end_grace
# A catch-up bubble ends with it (tools/catchup.py).
scoreboard players reset @s ck.bubble
execute if items entity @s armor.body *[custom_data~{monkey_grace:{}}] run item replace entity @s armor.body with minecraft:air
tellraw @s [{"text":"Your PvP grace is over: other players can hurt you now.","color":"red"}]
