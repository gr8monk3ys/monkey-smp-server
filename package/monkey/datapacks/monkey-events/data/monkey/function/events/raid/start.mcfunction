execute if score #raid ev.state matches 1.. run return run tellraw @s {"text":"It's already running. /function monkey:events/raid/stop ends it early.","color":"red"}
bossbar add monkey:raid "Faction Raid"
function monkey:events/raid/phase1
