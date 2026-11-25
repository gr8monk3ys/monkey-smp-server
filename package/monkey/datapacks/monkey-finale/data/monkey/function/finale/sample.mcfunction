# Macro at {x0, z0, d}: each player at the monument (survival, not in the arena) scores for their team.
$execute in minecraft:overworld as @a[x=$(x0),y=-64,z=$(z0),dx=$(d),dy=384,dz=$(d),gamemode=survival,tag=!ev.arena] run function monkey:finale/count
