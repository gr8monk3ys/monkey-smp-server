# Once a second, from the wardrobe's: every 5 seconds, while the goal is on and the season
# has launched, add up what the online players did and announce a milestone.
execute unless score #on rg matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
scoreboard players add #sec rg 1
execute if score #sec rg matches ..4 run return 0
scoreboard players set #sec rg 0
execute if score #idx rg matches 0 run function monkey:goal/count/logs
execute if score #idx rg matches 1 run function monkey:goal/count/mobs
execute if score #idx rg matches 2 run function monkey:goal/count/diamonds
execute if score #idx rg matches 3 run function monkey:goal/count/fish
execute if score #idx rg matches 4 run function monkey:goal/count/trades
execute if score #idx rg matches 5 run function monkey:goal/count/breed
execute if score #idx rg matches 6 run function monkey:goal/count/debris
execute if score #total rg matches ..-1 run scoreboard players set #total rg 0
execute if score #target rg matches ..0 run scoreboard players set #target rg 1
scoreboard players operation #pct rg = #total rg
scoreboard players operation #pct rg *= #100 rg
scoreboard players operation #pct rg /= #target rg
execute if score #pct rg matches 100.. unless score #said rg matches 100.. run function monkey:goal/reached
execute if score #pct rg matches 50.. unless score #said rg matches 50.. run function monkey:goal/half
