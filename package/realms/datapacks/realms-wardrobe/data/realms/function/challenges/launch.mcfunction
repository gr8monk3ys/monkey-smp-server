# Run by realms:rules/launch: this week's progress starts from zero. In Season I's launch week, challenges
# done before the launch (test play) don't count either; later seasons keep the ones they carried.
function realms:challenges/restart
execute if score #season rw.day matches 1 if score #week rc.week matches ..0 run scoreboard players reset * rw.challenges
execute if score #season rw.day matches 1 if score #week rc.week matches ..0 run scoreboard players reset * rw.challenges.seen
