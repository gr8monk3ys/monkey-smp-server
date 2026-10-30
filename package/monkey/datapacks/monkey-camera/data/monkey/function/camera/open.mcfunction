# Macro {minutes}: a camera window, announced (the usual one: 120).
execute unless score #on cm matches 1 run return run tellraw @s {"text":"The camera is off: /function monkey:camera/on first.","color":"red"}
$scoreboard players set #open cm $(minutes)
scoreboard players operation #open cm *= #60 cm
scoreboard players add #open cm 1
$tellraw @a ["",{"text":"Creator camera: ","color":"gold"},{"text":"for the next $(minutes) minutes, creators staff approved may film in spectator. Chat says who, when they start. They aren't in a faction, and they don't share where anyone is.","color":"gray"}]
