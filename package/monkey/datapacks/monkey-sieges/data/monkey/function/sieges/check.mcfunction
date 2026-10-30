# Each second while on: open, close or warn, from the countdowns.
execute unless score #synced sg matches 1 run return 0
execute unless score #launched rw.day matches 1 run return 0
execute if score #open sg matches 1 unless score #closes sg matches 1.. run return run function monkey:sieges/close
execute if score #open sg matches 1 if score #opens sg matches 1.. run return run function monkey:sieges/close
execute if score #open sg matches 1 run return 0
execute if score #opens sg matches ..0 if score #closes sg matches 1.. run return run function monkey:sieges/open
execute if score #opens sg matches 1..300 unless score #w2 sg matches 1 run return run function monkey:sieges/warn
execute if score #opens sg matches 1..1800 unless score #w1 sg matches 1 run return run function monkey:sieges/warn
