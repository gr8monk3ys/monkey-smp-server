# Macro {id}: the first's name read again where its holder stands, if it has none and they're online.
$execute unless data storage monkey:firsts held.$(id){name:""} run return 0
# Cleared first: with the holder offline nothing is read, and another player's name must not be kept.
data modify storage monkey:firsts name set value ""
$execute as @a[scores={rf.$(id)=1..},limit=1] at @s run function monkey:firsts/name
$data modify storage monkey:firsts held.$(id).name set from storage monkey:firsts name
$execute if data storage monkey:firsts held.$(id){name:""} run scoreboard players set #unnamed rf 1
