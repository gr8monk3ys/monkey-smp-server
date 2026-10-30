# Staff: ends a running finale where it is: the border stops where it has got to, no winner is named.
execute unless score #phase fn matches 1..3 run return run tellraw @s {"text":"No finale is running.","color":"red"}
execute in minecraft:overworld store result storage monkey:finale stop.size int 1 run worldborder get
function monkey:finale/stop_at with storage monkey:finale stop
scoreboard players set #phase fn 4
bossbar set monkey:finale visible false
tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"staff have stopped it. The border stays where it is.","color":"gold"}]
