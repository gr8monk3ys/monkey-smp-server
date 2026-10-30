scoreboard players set #open sg 0
scoreboard players operation #closed sg = #now sg
scoreboard players set #w1 sg 0
scoreboard players set #w2 sg 0
function monkey:sieges/lock
tellraw @a ["",{"text":"The siege window is closed.","color":"green","bold":true},{"text":" Claims are protected again. /trigger sieges says when the next one opens.","color":"gray"}]
execute as @a at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 0.6 1.2
