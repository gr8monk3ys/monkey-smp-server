function monkey:nights/load
execute unless score #phase nt.state matches 1.. run return run tellraw @s [{"text":"Nothing is running.","color":"red"}]
$scoreboard players set #new nt.timer $(minutes)
execute unless score #new nt.timer matches 1..600 run return run tellraw @s [{"text":"minutes must be 1 to 600.","color":"red"}]
scoreboard players operation #left nt.timer = #new nt.timer
scoreboard players operation #left nt.timer *= #60 nt.timer
execute store result bossbar monkey:nights max run scoreboard players get #left nt.timer
execute store result bossbar monkey:nights value run scoreboard players get #left nt.timer
function monkey:nights/bar
tellraw @s [{"text":"Time left set to ","color":"green"},{"score":{"name":"#new","objective":"nt.timer"},"color":"white"},{"text":" minutes.","color":"green"}]
