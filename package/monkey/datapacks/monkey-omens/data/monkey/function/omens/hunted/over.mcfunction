# From end: the hunt's bounty is over (a kill during it sets #phase 1 first, and stays claimable).
execute if score #phase om matches 1 run return 0
tellraw @a [{"text":"Hunted: ","color":"red","bold":true},{"text":"the bounty on ","color":"gray"},{"nbt":"target.name","storage":"monkey:omens","color":"white"},{"text":" is withdrawn: a kill from now on doesn't claim it.","color":"gray"}]
