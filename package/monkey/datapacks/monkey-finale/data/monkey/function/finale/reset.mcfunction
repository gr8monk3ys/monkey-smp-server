# Staff, test servers only: forget the finale, so it can start again. The border stays as it is.
execute store result storage monkey:finale on int 1 run scoreboard players get #on fn
scoreboard players reset * fn
execute store result score #on fn run data get storage monkey:finale on
scoreboard players set #started fn 0
scoreboard players set #phase fn 0
data remove storage monkey:finale result
bossbar set monkey:finale visible false
