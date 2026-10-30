# Macro {lo, hi}: their 7 days are up. The faction with more kills of the other wins.
$scoreboard players operation #ka dp.tmp = #$(lo).$(hi) dp.score
$scoreboard players operation #kb dp.tmp = #$(hi).$(lo) dp.score
$tellraw @a ["",{"text":"The war is over: ","color":"gold","bold":true},{"nbt":"names.f$(lo)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" against ","color":"gray"},{"nbt":"names.f$(hi)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" (7 days).","color":"gray"}]
$execute if score #ka dp.tmp > #kb dp.tmp run tellraw @a ["",{"nbt":"names.f$(lo)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" won, ","color":"gray"},{"score":{"name":"#$(lo).$(hi)","objective":"dp.score"},"color":"yellow"},{"text":" kills to ","color":"gray"},{"score":{"name":"#$(hi).$(lo)","objective":"dp.score"},"color":"yellow"},{"text":".","color":"gray"}]
$execute if score #kb dp.tmp > #ka dp.tmp run tellraw @a ["",{"nbt":"names.f$(hi)","storage":"monkey:factions","interpret":true,"color":"white"},{"text":" won, ","color":"gray"},{"score":{"name":"#$(hi).$(lo)","objective":"dp.score"},"color":"yellow"},{"text":" kills to ","color":"gray"},{"score":{"name":"#$(lo).$(hi)","objective":"dp.score"},"color":"yellow"},{"text":".","color":"gray"}]
$execute if score #ka dp.tmp = #kb dp.tmp run tellraw @a ["",{"text":"A draw, ","color":"gray"},{"score":{"name":"#$(lo).$(hi)","objective":"dp.score"},"color":"yellow"},{"text":" kills each.","color":"gray"}]
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.6 1
$function monkey:diplomacy/wars/ended {lo:$(lo),hi:$(hi),how:"time"}
$scoreboard players reset #$(lo).$(hi) dp.war
