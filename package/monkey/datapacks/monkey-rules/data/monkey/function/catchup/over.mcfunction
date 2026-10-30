# The hours ran out. Rule 26's grace lapses within two seconds, unless its own 48 hours still run.
scoreboard players reset @s ck.bubble
title @s actionbar {"text":"Your protection bubble is over.","color":"red"}
tellraw @s {"text":"Your protection bubble is over.","color":"red"}
