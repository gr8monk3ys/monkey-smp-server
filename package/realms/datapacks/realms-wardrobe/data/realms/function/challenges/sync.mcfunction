# Macro {week:N}: deploy/realms-week.sh runs it every hour (staff can too: docs/ADMIN.md). Starts week N
# unless it is already running: clears last week's progress (not in a world that had no week yet),
# then picks the three.
$execute if score #week rc.week matches $(week) run return 0
execute unless score #week rc.week matches -1 run function realms:challenges/restart
$scoreboard players set #week rc.week $(week)
function realms:challenges/pick
