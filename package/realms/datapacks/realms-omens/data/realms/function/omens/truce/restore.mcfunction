# PvP back on, unless something else turned it off meanwhile (the season lock, the launch hour) or
# staff turned it on again already.
execute if score #season_locked ev.state matches 1 run return 0
execute if score #launching realms.rules matches 1 run return 0
gamerule pvp true
