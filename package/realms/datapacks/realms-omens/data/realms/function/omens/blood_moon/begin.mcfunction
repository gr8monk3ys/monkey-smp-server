# Returns 1 when it starts: it waits for nightfall, then rises. Not on Peaceful (no mobs).
execute store result score #diff om run difficulty
execute if score #diff om matches 0 run return 0
scoreboard players set #state om 1
scoreboard players set #phase om 0
scoreboard players set #timer om 720
tellraw @a {"text":"The moon is coming up red tonight.","color":"dark_red","italic":true}
return 1
