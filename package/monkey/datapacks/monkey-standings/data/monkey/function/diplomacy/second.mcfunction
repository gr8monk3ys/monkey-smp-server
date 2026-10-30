schedule function monkey:diplomacy/second 20t replace
scoreboard players enable @a diplomacy
execute if score #launched rw.day matches 1 unless score #launched dp.state matches 1 run function monkey:diplomacy/launch
# Once a minute: has a 7-day war run its time?
scoreboard players add #wsec dp.tmp 1
execute if score #wsec dp.tmp matches 60.. run function monkey:diplomacy/wars/check
