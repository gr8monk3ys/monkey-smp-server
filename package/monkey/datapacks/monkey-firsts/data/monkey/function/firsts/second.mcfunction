scoreboard players enable @a firsts
execute if score #launched rw.day matches 1 run function monkey:firsts/clean
# Every 10 seconds, not every second: a holder can stay offline for days.
scoreboard players add #wait rf 1
execute if score #wait rf matches 10.. if score #unnamed rf matches 1.. run function monkey:firsts/rename
execute if score #wait rf matches 10.. run scoreboard players set #wait rf 0
schedule function monkey:firsts/second 20t replace
