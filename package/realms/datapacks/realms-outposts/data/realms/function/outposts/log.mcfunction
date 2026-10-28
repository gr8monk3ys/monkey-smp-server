# Macro {o, f}: a capture, numbered, for the Sunday recap (tools/outposts.py captures).
scoreboard players add #seq op 1
$data modify storage realms:outposts log append value {kind:"capture",o:$(o),f:$(f)}
execute store result storage realms:outposts log[-1].n int 1 run scoreboard players get #seq op
