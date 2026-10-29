schedule function monkey:drops/second 20t replace
execute if score #state dr matches 2 run function monkey:drops/countdown
execute if score #state dr matches 3 run function monkey:drops/landed
