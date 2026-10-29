# Macro {seconds:N}, from deploy/monkey-week.sh every hour: N seconds of the launch weekend are left on
# the wall clock. An open window the launch opened ends then (0 shuts it now); otherwise nothing.
execute unless score #founder.auto rw.day matches 1 run return 0
$scoreboard players set #founder.left rw.day $(seconds)
execute if score #founder.left rw.day matches ..0 run return run function monkey:wardrobe/founder/close
scoreboard players operation #founder.left rw.day *= #second rw.const
execute store result score #founder.until rw.day run time query gametime
scoreboard players operation #founder.until rw.day += #founder.left rw.day
