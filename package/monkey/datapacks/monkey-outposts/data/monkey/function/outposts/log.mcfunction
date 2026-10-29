# Macro {o, f}: a capture, numbered, for the Sunday recap (tools/outposts.py captures).
scoreboard players add #seq op 1
$data modify storage monkey:outposts log append value {kind:"capture",o:$(o),f:$(f)}
execute store result storage monkey:outposts log[-1].n int 1 run scoreboard players get #seq op
execute if data storage monkey:outposts log[500] run data remove storage monkey:outposts log[0]
