# Run by challenges/pick, once the week is known: a new week's goal, its name and target. The same
# week again (every server start) keeps what it has, so a target staff changed stays.
execute if score #week rg = #week rc.week run return 0
scoreboard players operation #week rg = #week rc.week
scoreboard players operation #idx rg = #week rc.week
execute if score #idx rg matches ..-1 run scoreboard players set #idx rg 0
scoreboard players set #n rg 7
scoreboard players operation #idx rg %= #n rg
execute if score #idx rg matches 0 run function monkey:goal/set/logs
execute if score #idx rg matches 1 run function monkey:goal/set/mobs
execute if score #idx rg matches 2 run function monkey:goal/set/diamonds
execute if score #idx rg matches 3 run function monkey:goal/set/fish
execute if score #idx rg matches 4 run function monkey:goal/set/trades
execute if score #idx rg matches 5 run function monkey:goal/set/breed
execute if score #idx rg matches 6 run function monkey:goal/set/debris
