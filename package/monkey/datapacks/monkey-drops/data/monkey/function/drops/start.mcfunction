# Staff: a drop at x, z now, whoever is online. It still checks the ground there.
execute if score #state dr matches 1.. run return run tellraw @s {"text":"A supply drop is on already. /function monkey:drops/stop ends it.","color":"red"}
$data modify storage monkey:drops spots set value [{x:$(x),z:$(z)}]
execute store result score #online dr if entity @a[gamemode=survival]
scoreboard players set #meteor dr 0
data modify storage monkey:drops name set value {text:"Supply drop"}
# A drop by hand doesn't use up tonight's: keep the night as it was.
data modify storage monkey:drops night set value 0
execute store result storage monkey:drops night int 1 run scoreboard players get #night dr
function monkey:drops/locate
tellraw @s {"text":"Checking the ground there; the announcement follows if it's dry land.","color":"gray"}
