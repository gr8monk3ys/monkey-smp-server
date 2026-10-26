# Once a second: let everyone use the trigger, count days and hours, mark founders, keep the launch
# weekend's window and the weekly challenges going, announce unlocks.
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
execute as @a run scoreboard players operation @s rw.hours = @s rw.play
execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase
scoreboard players operation @a rw.hours /= #hour rw.const
execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1
execute as @a unless score @s rw.lastday = #today rw.day run function realms:wardrobe/new_day
function realms:wardrobe/founder/second
function realms:challenges/second
execute as @a unless score @s rw.months.seen = @s rw.months run function realms:wardrobe/notice/months
execute as @a unless score @s rw.events.seen = @s rw.events run function realms:wardrobe/notice/events
execute as @a unless score @s rw.hallowtide.seen = @s rw.hallowtide run function realms:wardrobe/notice/hallowtide
execute as @a unless score @s rw.midwinter.seen = @s rw.midwinter run function realms:wardrobe/notice/midwinter
execute as @a unless score @s rw.midsummer.seen = @s rw.midsummer run function realms:wardrobe/notice/midsummer
execute as @a unless score @s rw.challenges.seen = @s rw.challenges run function realms:wardrobe/notice/challenges
execute as @a unless score @s rw.launch.seen = @s rw.launch run function realms:wardrobe/notice/launch
schedule function realms:wardrobe/second 20t replace
