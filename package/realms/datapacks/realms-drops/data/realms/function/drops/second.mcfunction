schedule function realms:drops/second 20t replace
execute if score #state dr matches 2 run function realms:drops/countdown
execute if score #state dr matches 3 run function realms:drops/landed
