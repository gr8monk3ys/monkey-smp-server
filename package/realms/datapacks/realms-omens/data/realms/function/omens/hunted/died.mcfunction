# As the hunted player, who died, not to a player (a player's kill ends the hunt first).
tellraw @a [{"text":"Hunted: ","color":"red","bold":true},{"nbt":"target.name","storage":"realms:omens","color":"white"},{"text":" died, but not to a player. The hunt is over.","color":"gray"}]
function realms:omens/end
