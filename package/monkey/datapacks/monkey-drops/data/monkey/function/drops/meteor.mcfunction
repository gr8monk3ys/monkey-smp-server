# A Meteor (tools/omens.py): a drop announced 5 minutes ahead, one chest with more in it. Run with the
# spots in storage like the try, and the same codes. It is extra: tonight's drop is kept as it was.
execute unless score #auto dr matches 1 run return 10
execute if score #state dr matches 1.. run return 11
execute if score #arena ev.state matches 1 run return 13
execute if score #raid ev.state matches 1.. run return 13
execute if score #anarchy ev.state matches 1.. run return 13
execute if score #season_locked ev.state matches 1 run return 13
execute unless data storage monkey:drops spots[0] run return 15
execute store result score #online dr if entity @a[gamemode=survival]
scoreboard players set #meteor dr 1
data modify storage monkey:drops name set value {text:"Meteor"}
data modify storage monkey:drops night set value 0
execute store result storage monkey:drops night int 1 run scoreboard players get #night dr
function monkey:drops/locate
return 1
