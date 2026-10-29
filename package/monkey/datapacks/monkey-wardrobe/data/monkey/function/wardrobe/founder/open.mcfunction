# Opens the launch weekend: monkey:rules/launch runs this (staff can too, if the launch didn't). Season I
# only. It lasts 31 hours of game time; deploy/monkey-week.sh moves the end to the end of Sunday,
# Pacific, on the wall clock.
execute unless score #season rw.day matches 1 run return run tellraw @s {"text":"Founder's Circlet is only for Season I's launch weekend.","color":"red"}
scoreboard players set #founder.open rw.day 1
scoreboard players set #founder.auto rw.day 1
execute store result score #founder.until rw.day run time query gametime
scoreboard players add #founder.until rw.day 2232000
tellraw @a [{"text":"Launch weekend: ","color":"gold"},{"text":"play 10 minutes before the end of Sunday (Pacific) to keep Founder's Circlet, a helm skin, for good.","color":"yellow"}]
