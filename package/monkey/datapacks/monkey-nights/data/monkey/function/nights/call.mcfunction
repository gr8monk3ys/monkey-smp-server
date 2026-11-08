$data modify storage monkey:nights call set value "$(block)"
title @a times 10 60 20
title @a subtitle {"storage":"monkey:nights","nbt":"call","color":"aqua"}
title @a title {"text":"Called-out block","color":"gold"}
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Called-out block: ","color":"yellow"},{"storage":"monkey:nights","nbt":"call","color":"aqua"},{"text":" (2 points for each faction that uses it in its base)","color":"gray"}]
