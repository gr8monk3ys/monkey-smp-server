# Macro {stamp:YYYYMMDD}: deploy/monkey-day.sh sends it at midnight UTC with that UTC date. Starts the day
# unless the day for that date already started, so a retry after a timeout never makes one date two days.
$execute if score #day.sent rw.day matches $(stamp) run return 0
$scoreboard players set #day.sent rw.day $(stamp)
function monkey:wardrobe/day
