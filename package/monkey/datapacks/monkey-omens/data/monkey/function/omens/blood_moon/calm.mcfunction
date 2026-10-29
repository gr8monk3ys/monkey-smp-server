# The end of a Blood Moon: the mobs' effects wear off in seconds, and the difficulty comes back, unless
# staff changed it meanwhile or the season was locked (it sets Peaceful).
scoreboard players reset @e[type=#monkey:omens/blood_moon,scores={om.blood=1..}] om.blood
execute unless score #phase om matches 1 run return 0
execute store result score #now om run difficulty
execute unless score #now om matches 3 run return 0
execute if score #season_locked ev.state matches 1 run return 0
execute if score #diff om matches 0 run difficulty peaceful
execute if score #diff om matches 1 run difficulty easy
execute if score #diff om matches 2 run difficulty normal
