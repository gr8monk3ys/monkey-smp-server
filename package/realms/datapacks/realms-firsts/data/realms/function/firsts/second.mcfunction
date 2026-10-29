scoreboard players enable @a firsts
execute if score #launched rw.day matches 1 run function realms:firsts/clean
schedule function realms:firsts/second 20t replace
