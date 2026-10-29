function monkey:drops/release with storage monkey:drops spot
execute if data storage monkey:drops spots[0] run return run function monkey:drops/locate
# None was dry land: no drop this time (the timer sends new spots in 10 minutes). A Meteor that found
# none ends here too (tools/omens.py then tries the evening's next omen).
scoreboard players set #state dr 0
scoreboard players set #meteor dr 0
data remove storage monkey:drops spot
