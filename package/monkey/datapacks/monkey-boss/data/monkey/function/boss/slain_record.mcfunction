$data modify storage monkey:boss acts.a$(act) merge value {state:"slain",faction:$(faction)}
$data modify storage monkey:boss acts.a$(act).name set from storage monkey:boss at.name
$execute store result storage monkey:boss acts.a$(act).week int 1 run scoreboard players get #week rc.week
