# Once a second: let everyone use the trigger, count days and hours, mark founders, keep the launch
# weekend's window, the weekly challenges, the first-week quest and the server goal going.
scoreboard players enable @a wardrobe
scoreboard players add @a rw.days 0
scoreboard players add @a rw.months 0
scoreboard players add @a rw.invites 0
scoreboard players add @a rw.tier 0
scoreboard players add @a rw.founder 0
scoreboard players add @a rw.events 0
scoreboard players add @a rw.hallowtide 0
scoreboard players add @a rw.midwinter 0
scoreboard players add @a rw.midsummer 0
scoreboard players add @a rw.playbase 0
scoreboard players add @a rw.challenges 0
scoreboard players add @a rw.launch 0
scoreboard players add @a rw.s2 0
scoreboard players add @a rw.champion 0
scoreboard players add @a rw.quest 0
scoreboard players add @a rw.kin 0
execute as @a run scoreboard players operation @s rw.hours = @s rw.play
execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase
scoreboard players operation @a rw.hours /= #hour rw.const
execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1
execute if score #season rw.day matches 2 run scoreboard players set @a rw.s2 1
execute as @a unless score @s rw.lastday = #today rw.day run function monkey:wardrobe/new_day
function monkey:wardrobe/founder/second
function monkey:challenges/second
function monkey:quest/second
function monkey:goal/second
schedule function monkey:wardrobe/second 20t replace
