schedule function monkey:finale/second 20t replace
# 0 before the finale; 1 the warnings, 2 the shrink, 3 the last hour, 4 after the close.
execute if score #phase fn matches 1..3 run function monkey:finale/tick
execute if score #phase fn matches 2.. run scoreboard players add #edge fn 1
execute if score #edge fn matches 5.. run function monkey:finale/edge
