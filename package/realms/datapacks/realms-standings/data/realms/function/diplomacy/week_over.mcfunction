# tools/standings.py close runs this once a week has closed: every war and pact offer ends; pacts stand.
execute if score #wars dp.state matches 1.. run tellraw @a [{"text":"The week is over, and so are its wars. ","color":"gold"},{"text":"Pacts stand. A leader can declare war again with /trigger diplomacy.","color":"gray"}]
scoreboard players reset * dp.war
scoreboard players reset * dp.offer
scoreboard players set #wars dp.state 0
