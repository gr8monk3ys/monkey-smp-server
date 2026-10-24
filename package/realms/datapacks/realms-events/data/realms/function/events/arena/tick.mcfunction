# Every tick while the arena is open (macro: the arena's points).
# Strength stays at the arena level: kills gain none, deaths cost none, nothing can be withdrawn.
scoreboard players set @a[tag=ev.arena] Strength_SMP+Strength_Level 3
scoreboard players reset @a[tag=ev.arena] Withdraw_Strength
execute as @a[tag=ev.arena] run function realms:events/arena/strength_sync
clear @a[tag=ev.arena] *[custom_data~{"Strength_SMP+Item":{}}]
# Players in the arena hold kit gear and nothing else (no bundle to hide gear in).
clear @a[tag=ev.arena] *[!custom_data~{realms_kit:{}}]
# Nothing dropped in the arena survives a tick, so nothing can be passed over the wall, and nothing
# that holds items (a chest minecart, a chest boat, a donkey) can carry gear or a bundle out: killing
# one drops its contents, which the next line removes. Kit gear stashed anywhere else is marked, and
# cleared from whoever takes it out (tick.mcfunction).
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=#realms:holds_items,distance=..$(size)]
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=minecraft:item,distance=..$(size)]
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run kill @e[type=minecraft:experience_orb,distance=..$(size)]
# Died: back to the waiting room, still in the arena.
$execute as @e[type=player,tag=ev.arena,scores={ev.deaths=1..}] in minecraft:overworld positioned $(px) $(py) $(pz) run tp @s ~ ~ ~
scoreboard players set @e[type=player,tag=ev.arena,scores={ev.deaths=1..}] ev.deaths 0
# Anyone in the arena who is somewhere else (a teleport, another dimension) is taken out.
tag @a[tag=ev.arena] add ev.away
$execute in minecraft:overworld positioned $(px) $(py) $(pz) run tag @a[tag=ev.arena,distance=..$(size)] remove ev.away
execute as @a[tag=ev.away] run function realms:events/arena/leave with storage realms:events arena
