function realms:drops/release with storage realms:drops spot
execute if data storage realms:drops spots[0] run return run function realms:drops/locate
# None was dry land: no drop this time (the timer sends new spots in 10 minutes).
scoreboard players set #state dr 0
data remove storage realms:drops spot
