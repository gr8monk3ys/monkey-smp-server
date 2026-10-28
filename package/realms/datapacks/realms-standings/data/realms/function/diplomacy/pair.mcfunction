# From #a and #b dp.tmp (two faction numbers): storage realms:diplomacy pair {a, b, lo, hi}, lo the smaller.
scoreboard players operation #lo dp.tmp = #a dp.tmp
scoreboard players operation #lo dp.tmp < #b dp.tmp
scoreboard players operation #hi dp.tmp = #a dp.tmp
scoreboard players operation #hi dp.tmp > #b dp.tmp
execute store result storage realms:diplomacy pair.a int 1 run scoreboard players get #a dp.tmp
execute store result storage realms:diplomacy pair.b int 1 run scoreboard players get #b dp.tmp
execute store result storage realms:diplomacy pair.lo int 1 run scoreboard players get #lo dp.tmp
execute store result storage realms:diplomacy pair.hi int 1 run scoreboard players get #hi dp.tmp
