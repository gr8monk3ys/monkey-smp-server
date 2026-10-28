# A player killed the hunted player (advancement realms:omens/hunted_kill). Staff check the kill as for
# any bounty, then claim it for them with standings' bounty/claim.
advancement revoke @s only realms:omens/hunted_kill
execute unless score #state om matches 4 run return 0
execute if entity @s[tag=ev.arena] run return 0
tellraw @a [{"text":"Hunted: ","color":"red","bold":true},{"selector":"@s","color":"white"},{"text":" killed ","color":"yellow"},{"nbt":"target.name","storage":"realms:omens","color":"white"},{"text":". Staff check the kill, then the bounty is theirs.","color":"yellow"}]
scoreboard players set #phase om 1
function realms:omens/end
