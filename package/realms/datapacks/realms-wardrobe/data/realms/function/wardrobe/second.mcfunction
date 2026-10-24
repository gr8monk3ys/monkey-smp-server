# Once a second: let everyone use the trigger, count days and hours, mark founders.
scoreboard players enable @a wardrobe
scoreboard players add @a rw.days 0
scoreboard players add @a rw.months 0
scoreboard players add @a rw.invites 0
scoreboard players add @a rw.tier 0
scoreboard players add @a rw.founder 0
execute as @a run scoreboard players operation @s rw.hours = @s rw.play
scoreboard players operation @a rw.hours /= #hour rw.const
execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1
execute as @a unless score @s rw.lastday = #today rw.day run function realms:wardrobe/new_day
schedule function realms:wardrobe/second 20t replace
