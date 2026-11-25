# Runs as a player who just used /trigger wardrobe: every value opens the menu.
function monkey:wardrobe/menu
scoreboard players set @s wardrobe 0
scoreboard players enable @s wardrobe
