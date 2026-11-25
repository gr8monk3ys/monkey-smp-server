# Once a second. The End is closed until staff run monkey:rules/open_end on Dragon Night.
execute unless score #end_open monkey.rules matches 1 in minecraft:the_end as @a[distance=0..] run function monkey:rules/leave_end
# The welcome, a few seconds after a first join so the loading screen doesn't swallow it.
execute as @a[scores={monkey.welcome=1}] run function monkey:rules/welcome
scoreboard players remove @a[scores={monkey.welcome=2..}] monkey.welcome 1
execute as @a[tag=!monkey.joined] run function monkey:rules/first_join
schedule function monkey:rules/second 20t replace
