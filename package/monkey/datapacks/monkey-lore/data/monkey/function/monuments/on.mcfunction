# Staff: players can use /trigger monument (docs/SEASONS.md, "Switches").
scoreboard players set #on mn 1
tellraw @s {"text":"Monument of the Month is on. Open a month with its open function (python tools/monuments.py plan lists them).","color":"green"}
