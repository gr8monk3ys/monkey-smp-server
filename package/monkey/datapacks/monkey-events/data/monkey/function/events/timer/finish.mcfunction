# Ends the event now, as if its time had run out: the "Event over" title and all.
execute unless score #timer ev.state matches 1.. run return run tellraw @s {"text":"No event timer is running.","color":"red"}
function monkey:events/timer/over
