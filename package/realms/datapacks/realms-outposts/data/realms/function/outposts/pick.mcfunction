# Macro cand {i, x, z}: an outpost that found its spot this survey skips the rest of its candidates.
execute if function realms:outposts/stopped run return run function realms:outposts/done
$execute if score #d$(i) op matches 1 run return run function realms:outposts/next
scoreboard players set #wait op 0
$execute in minecraft:overworld run forceload add $(x) $(z)
schedule function realms:outposts/check 20t replace
