$data modify storage monkey:boss acts.a$(act).state set value "$(state)"
$execute store result storage monkey:boss acts.a$(act).week int 1 run scoreboard players get #week rc.week
