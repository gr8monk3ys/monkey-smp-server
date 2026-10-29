# Macro {id:"red",name:"Red Monkeys"}, run holding the faction's banner: makes it the official flag.
# Each flag gets the next number. A copy made by crafting has the same number, so two flags with one
# number means one is a copy (B13).
execute unless items entity @s weapon.mainhand #minecraft:banners run return run tellraw @s {"text":"Hold the faction's banner in your main hand.","color":"red"}
$data modify storage monkey:events flag set value {id:"$(id)",name:"$(name)"}
execute store result storage monkey:events flag.n int 1 run scoreboard players add #flags ev.state 1
function monkey:events/flag/stamp with storage monkey:events flag
