# Macro cand {i, x, z}: an outpost that found its spot this survey skips the rest of its candidates.
execute if function monkey:outposts/stopped run return run function monkey:outposts/done
$execute if score #d$(i) op matches 1 run return run function monkey:outposts/next
scoreboard players set #wait op 0
$execute in minecraft:overworld run forceload add $(x) $(z)
schedule function monkey:outposts/check 20t replace
