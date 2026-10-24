execute if score #anarchy ev.state matches 1.. run return run tellraw @s {"text":"It's already running. /function realms:events/anarchy/stop ends it early.","color":"red"}
bossbar add realms:anarchy "Anarchy"
function realms:events/anarchy/phase1
