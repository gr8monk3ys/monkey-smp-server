# Once a second, from the wardrobe's (after its new_day, so rw.days is today's): the trigger, then, while
# the quest is on and the season has launched, sign up whoever is seen for the first time and check the
# open steps of those taking part. Nobody else costs more than the selector.
scoreboard players enable @a quest
execute unless score #on rq matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
execute as @a unless score @s rq.state matches -2147483648.. run function monkey:quest/join
execute as @a[scores={rq.state=1}] run function monkey:quest/check
