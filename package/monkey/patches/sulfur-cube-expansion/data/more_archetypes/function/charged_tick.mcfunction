particle minecraft:dust{color:[1.0,0.0,0.0],scale:1.0} ~ ~0.5 ~ 0.4 0.3 0.4 0 3

# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"): upstream's marker broke the button every tick
# and this function placed it again, two block changes a tick for each charged cube (Ledger logged every one: about
# 29 million rows a day on the live server). Now the button is placed only where there is air, and a cube on its own
# button keeps it: charged_tick_2 marks the block's marker (making one if it is gone), and the marker only takes the
# button away on a tick after no cube marked it.
execute at @s if block ~ ~ ~ #minecraft:air run fill ~ ~ ~ ~ ~ ~ minecraft:mangrove_button[powered=true,face=floor] replace #minecraft:air
execute at @s if block ~ ~ ~ minecraft:mangrove_button[powered=true,face=floor] run function more_archetypes:charged_tick_2
