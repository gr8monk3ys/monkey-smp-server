# Macro {name:"Alex"}: Alex is hunted, if online in survival outside the arena with the streak.
$execute unless entity @a[name=$(name),gamemode=survival,tag=!ev.arena] run return 0
$execute unless score $(name) om.streak matches 3.. run return 0
$function monkey:omens/hunted/on {name:"$(name)"}
return 1
