execute if score #anarchy ev.state matches 1.. run return run tellraw @s {"text":"It's already running. /function monkey:events/anarchy/stop ends it early.","color":"red"}
bossbar add monkey:anarchy "Anarchy"
function monkey:events/anarchy/phase1
