# Staff: the switch (docs/SEASONS.md, "Switches"). From Season II only.
execute unless score #season rw.day matches 2.. run return run tellraw @s {"text":"The border boss is for Season II on: this world is Season I (#season rw.day).","color":"red"}
scoreboard players set #on bs 1
tellraw @s {"text":"The border boss is on: the next border act raises one.","color":"gold"}
