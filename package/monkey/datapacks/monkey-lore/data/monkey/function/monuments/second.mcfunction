schedule function monkey:monuments/second 20t replace
execute unless score #on mn matches 1 run return 0
scoreboard players enable @a monument
execute as @a[scores={monument=1..}] run function monkey:monuments/use
