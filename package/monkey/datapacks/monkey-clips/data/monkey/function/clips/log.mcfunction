# Macro m: the villager's death is the log line (the server logs every villager's death with its name).
$summon minecraft:villager ~ -100 ~ {Tags:["cl.log"],Silent:1b,NoAI:1b,CustomName:"MONKEY-CLIP v=1|kind=$(kind)|title=$(title)|players=$(players)|factions=$(factions)|dim=$(dim)|pos=$(x),$(y),$(z)"}
kill @e[type=minecraft:villager,tag=cl.log]
