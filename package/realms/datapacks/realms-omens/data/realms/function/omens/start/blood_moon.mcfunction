# Staff: a Blood Moon at the next nightfall, whoever is online. It doesn't use up tonight's omen.
execute if score #state om matches 1.. run return run tellraw @s {"text":"An omen is on already. /function realms:omens/stop ends it.","color":"red"}
execute store result score #r om run function realms:omens/blood_moon/begin
execute unless score #r om matches 1 run return run tellraw @s {"text":"The game is on Peaceful: no mobs to rouse.","color":"red"}
tellraw @s {"text":"Blood Moon: it rises at the next nightfall.","color":"green"}
