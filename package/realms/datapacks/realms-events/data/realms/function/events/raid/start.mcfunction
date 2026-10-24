execute if score #raid ev.state matches 1.. run return run tellraw @s {"text":"It's already running. /function realms:events/raid/stop ends it early.","color":"red"}
bossbar add realms:raid "Faction Raid"
function realms:events/raid/phase1
