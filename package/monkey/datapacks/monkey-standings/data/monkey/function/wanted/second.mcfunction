schedule function monkey:wanted/second 20t replace
# A victim tag a kill didn't pick up (a death the killer's advancement didn't see) goes.
tag @a[tag=wt.victim] remove wt.victim
execute as @a unless score @s wt.id matches 1.. run function monkey:wanted/new_id
scoreboard players enable @a wanted
execute as @a[scores={wanted=1..}] run function monkey:wanted/use
