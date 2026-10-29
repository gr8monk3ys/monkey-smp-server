# 1 when a survey must stop: outposts turned off, or the season locked.
execute unless score #auto op matches 1 run return 1
execute if score #season_locked ev.state matches 1 run return 1
return 0
