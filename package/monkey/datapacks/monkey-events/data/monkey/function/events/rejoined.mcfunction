# A player who logged out came back.
scoreboard players reset @s ev.left
execute if entity @s[tag=ev.arena] run tellraw @s {"text":"You logged out in the arena, so you're out: your Strength is back.","color":"yellow"}
execute if entity @s[tag=ev.arena] run function monkey:events/arena/leave with storage monkey:events arena
# A flag carried out of a raid by logging out goes back to its faction.
execute unless score #raid ev.state matches 1.. run return 0
execute store result score #taken ev.state run clear @s *[custom_data~{monkey_flag:{}}]
execute if score #taken ev.state matches 1.. run tellraw @a [{"selector":"@s","color":"yellow"},{"text":" logged out with a flag. It goes back to its faction; staff will return it.","color":"yellow"}]
