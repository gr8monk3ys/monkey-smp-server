scoreboard players enable @a firsts
execute if score #launched rw.day matches 1 run function monkey:firsts/clean
execute if score #unnamed rf matches 1.. run function monkey:firsts/rename
schedule function monkey:firsts/second 20t replace
