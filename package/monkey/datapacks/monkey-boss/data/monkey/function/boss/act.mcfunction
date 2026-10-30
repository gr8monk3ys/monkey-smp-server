# Macro {act, x, z, delay}: sent by the border timer (tools/border.py) after it records border act N, or
# by staff. Each act is taken once (#act bs), so sending it again never makes a second boss.
execute unless score #on bs matches 1 run return 10
execute unless score #season rw.day matches 2.. run return 11
execute unless score #launched rw.day matches 1 run return 12
execute if score #season_locked ev.state matches 1 run return 13
$execute if score #act bs matches $(act).. run return 14
execute if score #state bs matches 1.. run return 15
$scoreboard players set #act bs $(act)
$data modify storage monkey:boss at set value {act:$(act),x:$(x),z:$(z),hp:0}
$data modify storage monkey:boss last set value {x:$(x),z:$(z)}
$data modify storage monkey:boss acts.a$(act) set value {state:"waiting",x:$(x),z:$(z),hp:0}
$scoreboard players set #wait bs $(delay)
scoreboard players set #state bs 1
# The spot's chunk stays loaded until the boss ends, so it can rise there and leave on time.
$execute in minecraft:overworld run forceload add $(x) $(z)
$tellraw @a ["",{"text":"Something stirs past the old edge. ","color":"dark_red","bold":true},{"text":"When the border has grown, The Edgewalker rises near ","color":"gold"},{"text":"$(x), $(z)","color":"yellow"},{"text":". The first to slay it takes a Server First for their faction. A staff event: within 96 blocks of it anyone can fight anyone (rule 41).","color":"gold"}]
return 1
