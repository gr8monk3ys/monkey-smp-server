# Find an elytra: the advancement fired. It is taken back first, so it can fire again if this didn't
# count; once the first is claimed its condition stops it firing at all.
advancement revoke @s only realms:firsts/elytra
execute if score #elytra rf matches 1.. run return 0
execute unless score #launched rw.day matches 1 run return 0
# Not once the season is locked (the finale: adventure mode, the world archived).
execute if score #season_locked ev.state matches 1 run return 0
# Not with kit gear in the event arena, and not in creative or spectator (staff).
execute if entity @s[tag=ev.arena] run return 0
execute unless entity @s[gamemode=!creative,gamemode=!spectator] run return 0
# Not for elytra carried over from test play: this player must have been seen
# without one on them since the launch (realms:firsts/clean).
execute unless entity @s[tag=rf.clean.elytra] run return 0
function realms:firsts/claim/elytra
