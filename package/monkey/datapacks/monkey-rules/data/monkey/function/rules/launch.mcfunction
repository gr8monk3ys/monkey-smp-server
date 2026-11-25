# Staff run this once, at launch. PvP and the Nether are open from the start; the End waits for
# Dragon Night.
scoreboard players set #end_open monkey.rules 0
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Welcome to the new season! PvP and the Nether are open. The End opens on Dragon Night.","color":"yellow"}]
# The launch weekend opens for Founder's Circlet (tools/wardrobe.py), and this week's challenges start
# from zero, so test play before the launch doesn't count (tools/challenges.py). Only the first launch
# opens it: challenges/launch sets #launched, and a launch run again by mistake after the weekend would
# open a window that no wall-clock sync closes any more.
execute unless score #launched rw.day matches 1 run function monkey:wardrobe/founder/open
# Server Firsts (tools/firsts.py): a first claimed before the first launch is cleared. Before
# challenges/launch, which sets #launched.
function monkey:firsts/launch
function monkey:challenges/launch
