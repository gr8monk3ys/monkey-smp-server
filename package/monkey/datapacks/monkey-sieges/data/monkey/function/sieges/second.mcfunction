schedule function monkey:sieges/second 20t replace
scoreboard players enable @a sieges
execute as @a[scores={sieges=1..}] run function monkey:sieges/show
# The clock: a minute every 60 seconds between the timer's runs, which set it right.
scoreboard players add #sec sg 1
execute if score #sec sg matches 60.. run scoreboard players add #now sg 1
execute if score #sec sg matches 60.. run scoreboard players set #sec sg 0
execute if score #opens sg matches 1.. run scoreboard players remove #opens sg 1
execute if score #closes sg matches 1.. run scoreboard players remove #closes sg 1
execute if score #on sg matches 1 run function monkey:sieges/check
