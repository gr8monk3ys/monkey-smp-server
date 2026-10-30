# As a player who just found the last page.
tellraw @a ["",{"selector":"@s","color":"white"},{"text":" has found every page of the Knotkeeper's chronicle: a Knotkeeper!","color":"dark_aqua"}]
# The title, unless they show another (a supporter color or a title is never taken away for it).
execute unless entity @s[team=] run return run tellraw @s {"text":"You already show a title or a supporter color, so it stays. Ask staff if you'd rather show Knotkeeper.","color":"gray"}
team join title_knotkeeper @s
