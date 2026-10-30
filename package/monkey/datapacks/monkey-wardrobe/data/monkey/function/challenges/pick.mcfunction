# This week's three: challenge (#week mod how many) of each kind, the same as tools/challenges.py picks.
scoreboard players operation #solo rc.week = #week rc.week
execute if score #solo rc.week matches ..-1 run scoreboard players set #solo rc.week 0
scoreboard players set #count rc.week 10
scoreboard players operation #solo rc.week %= #count rc.week
scoreboard players operation #faction rc.week = #week rc.week
execute if score #faction rc.week matches ..-1 run scoreboard players set #faction rc.week 0
scoreboard players set #count rc.week 5
scoreboard players operation #faction rc.week %= #count rc.week
scoreboard players operation #explore rc.week = #week rc.week
execute if score #explore rc.week matches ..-1 run scoreboard players set #explore rc.week 0
scoreboard players set #count rc.week 4
scoreboard players operation #explore rc.week %= #count rc.week
function monkey:goal/pick
