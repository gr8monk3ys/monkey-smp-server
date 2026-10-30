# Once a minute (diplomacy/second): ends each 7-day war whose time is up.
scoreboard players set #wsec dp.tmp 0
execute unless data storage monkey:diplomacy wars[0] run return 0
execute unless score #now sg matches 1.. run return 0
data modify storage monkey:diplomacy scan set from storage monkey:diplomacy wars
function monkey:diplomacy/wars/next
