# From monkey:rules/first_join, as a player the server has never seen: the kit for a late first join
# (week 3 or later of a launched season), while the switch is on. The welcome says so.
execute unless score #on ck matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
execute unless score #week rc.week matches 3.. run return 0
function monkey:catchup/give
