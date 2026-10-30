# Once, the first second after the launch (monkey:rules/launch sets #launched rw.day): nothing from
# before it counts. Declarations can't be made before it; this clears anything staff set by hand.
scoreboard players reset * dp.war
scoreboard players reset * dp.pact
scoreboard players reset * dp.offer
scoreboard players reset * dp.pacts
scoreboard players reset * dp.last
scoreboard players reset * st.warkills
scoreboard players reset * dp.until
scoreboard players reset * dp.score
scoreboard players reset * dp.next
data modify storage monkey:diplomacy log set value []
data modify storage monkey:diplomacy wars set value []
scoreboard players set #ended dp.state 0
scoreboard players set #launched dp.state 1
