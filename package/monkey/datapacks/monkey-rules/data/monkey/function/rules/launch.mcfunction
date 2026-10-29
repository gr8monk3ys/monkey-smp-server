# Rule 23. An admin runs this once, at launch: PvP and the Nether close for 60 minutes.
gamerule pvp false
gamerule allow_entering_nether_using_portals false
scoreboard players set #end_open monkey.rules 0
# Rule 26: the season starts with nobody on grace (a test player's is gone), and nobody who first
# joins in the launch hour gets one.
scoreboard players reset * monkey.grace
scoreboard players reset * end_grace
scoreboard players set #launching monkey.rules 1
schedule function monkey:rules/launch_over 3600s replace
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Welcome to Season I! PvP, the Nether and the End are closed for the first 60 minutes.","color":"yellow"}]
# The launch weekend opens for Founder's Circlet (tools/wardrobe.py), and this week's challenges start
# from zero, so test play before the launch doesn't count (tools/challenges.py). Only the first launch
# opens it: challenges/launch sets #launched, and a launch run again by mistake after the weekend would
# open a window that no wall-clock sync closes any more.
execute unless score #launched rw.day matches 1 run function monkey:wardrobe/founder/open
# Server Firsts (tools/firsts.py): a first claimed before the first launch is cleared. Before
# challenges/launch, which sets #launched.
function monkey:firsts/launch
function monkey:challenges/launch
