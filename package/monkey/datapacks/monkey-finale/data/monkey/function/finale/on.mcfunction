# Staff: the switch (docs/SEASONS.md, "Switches"). From Season II only.
execute unless score #season rw.day matches 2.. run return run tellraw @s {"text":"The finale is for Season II on: this world is Season I (#season rw.day).","color":"red"}
scoreboard players set #on fn 1
tellraw @s {"text":"The finale is on: the border timer starts it at the finale's time.","color":"gold"}
