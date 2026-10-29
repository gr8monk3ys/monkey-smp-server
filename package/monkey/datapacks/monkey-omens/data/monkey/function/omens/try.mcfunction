# The evening's omen: deploy/monkey-omens.sh calls this every 10 minutes from the evening's start until
# 10 PM, after putting the order (and the meteor's spots, the hunt's names) in storage monkey:omens. Returns
# why it didn't start (tools/omens.py TRY_CODES).
execute unless score #auto om matches 1 run return 20
execute unless score #launched rw.day matches 1 run return 26
execute if score #state om matches 1.. run return 21
$execute if score #night om matches $(night) run return 22
execute if score #arena ev.state matches 1 run return 23
execute if score #raid ev.state matches 1.. run return 23
execute if score #anarchy ev.state matches 1.. run return 23
execute if score #season_locked ev.state matches 1 run return 23
execute if score #state dr matches 1.. run return 24
execute store result score #online om if entity @a[gamemode=survival]
execute if score #online om < #min om run return 25
$data modify storage monkey:omens tonight set value {night:$(night)}
$scoreboard players set #tonight om $(night)
$scoreboard players set #late om $(late)
execute store result score #r om run function monkey:omens/pick
execute unless score #r om matches 1 run return 27
scoreboard players operation #prev om = #night om
scoreboard players operation #night om = #tonight om
function monkey:omens/record with storage monkey:omens tonight
return 1
