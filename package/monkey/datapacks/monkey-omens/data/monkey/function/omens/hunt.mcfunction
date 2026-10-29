# Staff, macro {name:"Alex"}: Alex is hunted for 30 minutes, whatever their streak.
execute if score #state om matches 1.. run return run tellraw @s {"text":"An omen is on already. /function monkey:omens/stop ends it.","color":"red"}
$execute unless entity @a[name=$(name),gamemode=survival,tag=!ev.arena] run return run tellraw @s {"text":"$(name) isn't online in survival (or is in the arena).","color":"red"}
$data modify storage monkey:omens target set value {name:"$(name)"}
$function monkey:omens/hunted/on {name:"$(name)"}
