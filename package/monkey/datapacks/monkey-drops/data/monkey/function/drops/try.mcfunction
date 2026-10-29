# The weeknight drop: deploy/monkey-drops.sh calls this every 10 minutes in drop hours, after putting
# the spots in storage monkey:drops spots. Returns why it didn't start (tools/drops.py TRY_CODES).
execute unless score #auto dr matches 1 run return 10
execute if score #state dr matches 1.. run return 11
$execute if score #night dr matches $(night) run return 12
execute if score #arena ev.state matches 1 run return 13
execute if score #raid ev.state matches 1.. run return 13
execute if score #anarchy ev.state matches 1.. run return 13
execute if score #season_locked ev.state matches 1 run return 13
execute store result score #online dr if entity @a[gamemode=survival]
execute if score #online dr < #min dr run return 14
execute unless data storage monkey:drops spots[0] run return 15
scoreboard players set #meteor dr 0
data modify storage monkey:drops name set value {text:"Supply drop"}
$data modify storage monkey:drops night set value $(night)
function monkey:drops/locate
return 1
