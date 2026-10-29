schedule function realms:diplomacy/second 20t replace
scoreboard players enable @a diplomacy
execute if score #launched rw.day matches 1 unless score #launched dp.state matches 1 run function realms:diplomacy/launch
