# Once a second, from the wardrobe's: the trigger, days this week, a weekly hello, and progress on the
# three challenges that are on.
scoreboard players enable @a challenges
execute as @a unless score @s rc.lastday = #today rw.day run function monkey:challenges/day
execute as @a unless score @s rc.seen = #week rc.week run function monkey:challenges/greet
execute if score #solo rc.week matches 0 as @a run function monkey:challenges/progress/logs
execute if score #solo rc.week matches 1 as @a run function monkey:challenges/progress/days
execute if score #solo rc.week matches 2 as @a run function monkey:challenges/progress/iron
execute if score #solo rc.week matches 3 as @a run function monkey:challenges/progress/hostiles
execute if score #solo rc.week matches 4 as @a run function monkey:challenges/progress/fish
execute if score #solo rc.week matches 5 as @a run function monkey:challenges/progress/diamonds
execute if score #solo rc.week matches 6 as @a run function monkey:challenges/progress/breed
execute if score #solo rc.week matches 7 as @a run function monkey:challenges/progress/trade
execute if score #solo rc.week matches 8 as @a run function monkey:challenges/progress/enchant
execute if score #solo rc.week matches 9 as @a run function monkey:challenges/progress/debris
execute if score #faction rc.week matches 0 as @a run function monkey:challenges/progress/event
execute if score #faction rc.week matches 1 as @a run function monkey:challenges/progress/raid
execute if score #faction rc.week matches 2 as @a run function monkey:challenges/progress/fortress
execute if score #faction rc.week matches 3 as @a run function monkey:challenges/progress/breezes
execute if score #faction rc.week matches 4 as @a run function monkey:challenges/progress/brutes
execute if score #explore rc.week matches 0 as @a run function monkey:challenges/progress/loot
execute if score #explore rc.week matches 1 as @a run function monkey:challenges/progress/structures
execute if score #explore rc.week matches 2 as @a run function monkey:challenges/progress/nether
execute if score #explore rc.week matches 3 as @a run function monkey:challenges/progress/rare
