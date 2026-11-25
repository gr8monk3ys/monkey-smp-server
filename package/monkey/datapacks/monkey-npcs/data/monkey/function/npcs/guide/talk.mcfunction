# Run by the Guide's FancyNpcs right-click action, from the server console, as the player who clicked:
#   execute as {player} run function monkey:npcs/guide/talk
# (docs/ADMIN.md, "Spawn NPCs"). The console's permission lets it show a dialog.
execute unless entity @s[type=minecraft:player] run return run say Run it as a player: execute as <player> run function monkey:npcs/guide/talk
# A step of the first-week quest (tools/quest.py).
scoreboard players set @s rq.guide 1
dialog show @s monkey:npcs/guide
