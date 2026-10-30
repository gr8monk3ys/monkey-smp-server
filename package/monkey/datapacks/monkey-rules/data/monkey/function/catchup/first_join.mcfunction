# From monkey:rules/first_join, as a player the server has never seen: the kit and bubble for a late
# first join (week 4 or later of a launched season), while the switch is on.
execute unless score #on ck matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
execute unless score #week rc.week matches 4.. run return 0
function monkey:catchup/grant
