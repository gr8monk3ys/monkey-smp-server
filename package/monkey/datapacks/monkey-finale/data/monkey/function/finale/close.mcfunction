scoreboard players set #phase fn 4
bossbar set monkey:finale visible false
scoreboard players set #best fn 0
scoreboard players set #win fn 0
scoreboard players set #tie fn 0
scoreboard players set #n fn 1
function monkey:finale/pick
execute if score #tie fn matches 1 run scoreboard players set #win fn 0
data modify storage monkey:finale result set value {faction:0,points:0,tie:0,week:-1}
execute store result storage monkey:finale result.faction int 1 run scoreboard players get #win fn
execute store result storage monkey:finale result.points int 1 run scoreboard players get #best fn
execute store result storage monkey:finale result.tie int 1 run scoreboard players get #tie fn
execute store result storage monkey:finale result.week int 1 run scoreboard players get #week rc.week
execute if score #best fn matches 0 run tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"it is over. Nobody held the monument, so nobody wins it.","color":"gold"}]
execute if score #tie fn matches 1 run tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"it is over, and it is a tie for the monument. Staff decide the winner.","color":"gold"}]
execute if score #win fn matches 1.. run function monkey:finale/won with storage monkey:finale result
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 0.6
