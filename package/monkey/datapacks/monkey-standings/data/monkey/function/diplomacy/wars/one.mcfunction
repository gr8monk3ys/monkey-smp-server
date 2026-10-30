$execute if score #$(lo).$(hi) dp.until <= #now sg run function monkey:diplomacy/wars/over {lo:$(lo),hi:$(hi)}
# One that lost its end (staff reset scores by hand) leaves the list.
$execute unless score #$(lo).$(hi) dp.until matches -2147483648.. run data remove storage monkey:diplomacy wars[{lo:$(lo),hi:$(hi)}]
