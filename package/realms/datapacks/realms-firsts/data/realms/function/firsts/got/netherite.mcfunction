# Wear full Netherite: the advancement fired. It is taken back first, so it can fire again if this didn't
# count; once the first is claimed its condition stops it firing at all.
advancement revoke @s only realms:firsts/netherite
execute if score #netherite rf matches 1.. run return 0
execute unless score #launched rw.day matches 1 run return 0
# Not once the season is locked (the finale: adventure mode, the world archived).
execute if score #season_locked ev.state matches 1 run return 0
# Not with kit gear in the event arena, and not in creative or spectator (staff).
execute if entity @s[tag=ev.arena] run return 0
execute unless entity @s[gamemode=!creative,gamemode=!spectator] run return 0
# Rule 24: while realms-no-netherite-armor is on it stamps #netherite_rule every second, and
# takes the armor off within one. No stamp at all (no such pack): the rule isn't there.
execute store result score #age rf run time query gametime
scoreboard players operation #age rf -= #netherite_rule realms.rules
execute if score #age rf matches ..100 run return 0
function realms:firsts/claim/netherite
