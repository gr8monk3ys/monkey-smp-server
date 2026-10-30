# Macro at {act, x, z, hp}: the record (news, recap, tools/boss.py status) and the announcement.
$data modify storage monkey:boss acts.a$(act) set value {state:"risen",x:$(x),z:$(z),hp:$(hp)}
$execute store result storage monkey:boss acts.a$(act).week int 1 run scoreboard players get #week rc.week
$tellraw @a ["",{"text":"The Edgewalker has risen ","color":"dark_red","bold":true},{"text":"near ","color":"gold"},{"text":"$(x), $(z)","color":"yellow"},{"text":" in the Overworld, with ","color":"gold"},{"text":"$(hp)","color":"red"},{"text":" health. It leaves in 90 minutes if nobody slays it. A staff event until then: within 96 blocks of it anyone can fight anyone (rule 41).","color":"gold"}]
