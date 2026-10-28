# Open a trial vault: the advancement fired. It is taken back first, so it can fire again if this didn't
# count; once the first is claimed its condition stops it firing at all.
advancement revoke @s only realms:firsts/vault
execute if score #vault rf matches 1.. run return 0
execute unless score #launched rw.day matches 1 run return 0
# Not with kit gear in the event arena, and not in creative or spectator (staff).
execute if entity @s[tag=ev.arena] run return 0
execute unless entity @s[gamemode=!creative,gamemode=!spectator] run return 0
function realms:firsts/claim/vault
