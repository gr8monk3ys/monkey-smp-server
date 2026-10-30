# This week's goal, one chat line (the challenges page and the weekly hello).
execute unless score #on rg matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
tellraw @s [" ",{"text":"Server goal  ","color":"gray"},{"nbt":"name","storage":"monkey:goal","color":"yellow"},{"text":"  ","color":"gray"},{"score":{"name":"#total","objective":"rg"},"color":"white"},{"text":"/","color":"gray"},{"score":{"name":"#target","objective":"rg"},"color":"white"},{"nbt":"status","storage":"monkey:goal","color":"green"}]
