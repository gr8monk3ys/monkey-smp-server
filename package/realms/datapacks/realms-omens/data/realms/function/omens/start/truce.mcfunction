# Staff: a Truce Hour now. It doesn't use up tonight's omen.
execute if score #state om matches 1.. run return run tellraw @s {"text":"An omen is on already. /function realms:omens/stop ends it.","color":"red"}
execute store result score #r om run function realms:omens/truce/begin
execute unless score #r om matches 1 run return run tellraw @s {"text":"PvP is off already.","color":"red"}
