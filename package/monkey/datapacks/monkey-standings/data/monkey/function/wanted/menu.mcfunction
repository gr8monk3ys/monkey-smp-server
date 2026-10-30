# The Most Wanted (from the hourly board run), then a button for each rival online.
tellraw @s [{"text":"The wanted board\n","color":"gold","bold":true},{"nbt":"wanted","storage":"monkey:standings","interpret":true},{"text":"Post a bounty on a rival who is online: one every 12 hours. Kill a wanted player in a fair fight outside the arena to claim every bounty on them: the Bounty Hunter title and a line in chat. Nothing else: no items, no points.","color":"gray"}]
execute unless score #launched rw.day matches 1 run return run tellraw @s {"text":"Bounties open when the season launches.","color":"gray"}
execute unless score @s st.faction matches 1.. run return run tellraw @s {"text":"Join a faction first: bounties are between factions.","color":"gray"}
tag @s add wt.asker
scoreboard players set #rows wt 0
execute as @a[tag=!wt.asker,scores={st.faction=1..},limit=20] unless score @s st.faction = @a[tag=wt.asker,limit=1] st.faction run function monkey:wanted/row
execute if score #rows wt matches 0 run tellraw @s {"text":"No rivals online right now.","color":"gray"}
tag @s remove wt.asker
