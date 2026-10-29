# Staff, macro {i:1}: outpost i is held by nobody (say when it was taken against the rules).
$scoreboard players set #v op $(i)
execute unless score #v op matches 1..4 run return run tellraw @s {"text":"Outposts are 1 North, 2 East, 3 South and 4 West: release {i:1}","color":"red"}
$function monkey:outposts/o/$(i)/release
$tellraw @a ["",{"text":"Outposts: ","color":"gold","bold":true},{"text":"staff freed outpost $(i): nobody holds it now.","color":"yellow"}]
