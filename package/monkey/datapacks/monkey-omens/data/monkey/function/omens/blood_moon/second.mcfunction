scoreboard players remove #timer om 1
execute store result score #now om run time query minecraft:day
# It rises at nightfall only, so it never comes up just before dawn.
execute if score #phase om matches 0 if score #now om matches 13000..14000 run return run function monkey:omens/blood_moon/rise
execute if score #phase om matches 0 if score #timer om matches ..0 run return run function monkey:omens/blood_moon/fade
execute if score #phase om matches 0 run return 0
execute unless score #now om matches 13000..22999 run return run function monkey:omens/blood_moon/dawn
execute if score #timer om matches ..0 run return run function monkey:omens/blood_moon/dawn
scoreboard players operation #mins om = #timer om
scoreboard players add #mins om 59
scoreboard players operation #mins om /= #60 om
execute store result bossbar monkey:omen value run scoreboard players get #timer om
bossbar set monkey:omen players @a
bossbar set monkey:omen name [{"text":"","color":"red"},{"text":"Blood Moon: ","bold":true},{"text":"until dawn, at most "},{"score":{"name":"#mins","objective":"om"},"color":"white"},{"text":" min","color":"red"}]
execute as @a[gamemode=survival,tag=!ev.arena] at @s if dimension minecraft:overworld as @e[type=#monkey:omens/blood_moon,distance=..48] run function monkey:omens/blood_moon/rouse
