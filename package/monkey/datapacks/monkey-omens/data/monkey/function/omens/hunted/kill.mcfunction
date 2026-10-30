# A player killed the hunted player (advancement monkey:omens/hunted_kill). Staff check the kill as for
# any bounty, then claim it for them with standings' bounty/claim.
advancement revoke @s only monkey:omens/hunted_kill
execute unless score #state om matches 4 run return 0
execute if entity @s[tag=ev.arena] run return 0
tellraw @a [{"text":"Hunted: ","color":"red","bold":true},{"selector":"@s","color":"white"},{"text":" killed ","color":"yellow"},{"nbt":"target.name","storage":"monkey:omens","color":"white"},{"text":". Staff check the kill, then the bounty is theirs.","color":"yellow"}]
scoreboard players set #phase om 1
data modify storage monkey:omens clip set value {kind:"hunted",title:"The Hunted player is down"}
data modify storage monkey:omens clip.other set from storage monkey:omens target.name
function monkey:clips/mark with storage monkey:omens clip
function monkey:omens/end
