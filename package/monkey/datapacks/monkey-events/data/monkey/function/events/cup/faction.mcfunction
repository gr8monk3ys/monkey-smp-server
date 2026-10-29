# Macro {id:"red",name:"Red Monkeys"}: puts a faction on the Cup with 0 points.
$scoreboard players add $(id) ev.cup 0
$scoreboard players display name $(id) ev.cup "$(name)"
