# The end of a Blood Moon: the mobs still loaded calm down, and the difficulty comes back, unless staff
# changed it meanwhile or the season was locked (it sets Peaceful).
effect clear @e[tag=om.roused] minecraft:speed
effect clear @e[tag=om.roused] minecraft:resistance
scoreboard players reset @e[tag=om.roused] om.blood
tag @e[tag=om.roused] remove om.roused
execute unless score #phase om matches 1 run return 0
execute store result score #now om run difficulty
execute unless score #now om matches 3 run return 0
execute if score #season_locked ev.state matches 1 run return 0
execute if score #diff om matches 1 run difficulty easy
execute if score #diff om matches 2 run difficulty normal
