# Staff, macro {n:300}: this week's target is n (until the week turns). A milestone already passed is
# not said again; one now passed is said within seconds.
$scoreboard players set #target rg $(n)
tellraw @s ["",{"text":"This week's server goal target: ","color":"green"},{"score":{"name":"#target","objective":"rg"},"color":"white"}]
