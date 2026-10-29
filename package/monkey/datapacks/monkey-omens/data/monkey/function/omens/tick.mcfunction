# Kill streaks, for Hunted: player kills outside the event arena add up, from the launch on; dying
# outside the arena starts again from 0.
execute if score #launched rw.day matches 1 as @a[scores={om.pk=1..},tag=!ev.arena] run scoreboard players operation @s om.streak += @s om.pk
scoreboard players set @a[scores={om.pk=1..}] om.pk 0
execute if score #state om matches 4 as @a[scores={om.hunt=1..,om.deaths=1..}] run function monkey:omens/hunted/died
scoreboard players set @a[scores={om.deaths=1..},tag=!ev.arena] om.streak 0
scoreboard players set @a[scores={om.deaths=1..}] om.deaths 0
